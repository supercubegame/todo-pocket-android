#!/usr/bin/env python3
"""Synthetic native multi-note export. No receiver, OCR, real photos or LMK claim."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import xml.etree.ElementTree as ET
import zipfile
import verify_note_management as note_management

SCOPE = "NATIVE_TWO_NOTE_TEXT_SAF_NOT_OCR_RECEIVER_OR_PROCESS_LOSS"
FORMATS = (("MARKDOWN", "Markdown图片包", "PocketTodo-notes.zip"),
           ("PDF", "PDF", "PocketTodo-notes.pdf"),
           ("PNG_ZIP", "分段PNG图片包", "PocketTodo-pages.zip"))
STEPS = ["ui_created_second_note", "empty_note_selection_blocked",
         "note_cancel_preserves_state", "content_cancel_preserves_state"]
PER_FORMAT = ["explicit_reverse_clicks_private_excluded", "empty_content_blocked",
              "unchecked_save_blocked", "picker_cancel_preserves_state", "saved_and_independently_read",
              "all_tables_media_unchanged", "same_revision_second_note_privacy",
              "stale_publication_refused", "stale_refusal_preserves_state", "privacy_fixture_restored"]
LABELS = STEPS + [step + "_" + kind for kind, _, _ in FORMATS for step in PER_FORMAT]
EXPECTED = "# Pocket Todo\n\nSecond edited\n\nBatchsecond\n\n"
SUMMARY_LABELS = ["all_same_title_and_empty_notes", "second_activity_isolated",
                  "restart_all_notes", "restart_second_activity",
                  "same_revision_privacy", "newly_private_text_hidden",
                  "privacy_fixture_restored", "all_tables_media_unchanged"]
RENAME_LABELS = ["cancel_readonly", "blank_blocked_readonly", "same_title_noop",
                 "same_title_target_only", "restart_title_persisted", "duplicate_title_allowed"]
DELETE_UI_LABELS = ["preview_exact_identity_counts", "cancel_readonly", "unchecked_blocked_readonly",
                    "process_loss_readonly", "fresh_preview_unchecked", "same_title_target_only",
                    "all_media_preserved", "restart_deletion_and_sibling_persisted"]
DELETE_UI_SCOPE = "NATIVE_NOTE_DELETE_EXACT_ID_CONSENT_FORCE_STOP_RESTART_NOT_LMK"
ORDER_UI_LABELS = ["boundary_controls", "singleton_disabled_readonly",
                   "same_title_up_exact_state", "restart_up_summary_order",
                   "same_title_down_exact_state", "restart_down_summary_order",
                   "original_order_restored_two_revisions", "all_media_preserved"]
ORDER_UI_SCOPE = "NATIVE_NOTE_ORDER_STABLE_ID_FORCE_STOP_RESTART_NOT_LMK"

EDITOR_ORDER_LABELS = ["up_fresh_default_first", "up_picker_order_cancel_readonly",
                       "up_same_title_identity_readonly", "down_fresh_default_first",
                       "down_picker_order_cancel_readonly", "down_same_title_identity_readonly"]
EDITOR_ORDER_SCOPE = "NATIVE_REORDER_EDITOR_INDEXED_PICKER_DISTINCT_BODY_WITNESS_NOT_LMK"


def editor_picker_check(rows, actual):
    assert rows and len({r[0] for r in rows}) == len(rows)
    expected = [str(i+1)+". "+row[2] for i, row in enumerate(rows)]
    assert actual == expected, "editor picker order, membership or duplicate entry differs"


def editor_selection_check(data, owner, note, observed):
    # This is a discriminating visible body witness, not exhaustive/offscreen body validation.
    rows = [r for r in data["notes"] if r[1] == owner]
    ids = [r[0] for r in rows]
    assert note in ids and len(ids) == len(set(ids))
    index = ids.index(note)
    expected_header = rows[index][2]+" · "+str(index+1)+" / "+str(len(rows))
    headers = [n.get("text") for n in observed if n.get("content-desc") == "note-current"]
    assert headers == [expected_header], "editor selected title/index differs"
    blocks = sorted((r for r in data["blocks"] if r[0] == note), key=lambda r: r[2])
    empty = [n for n in observed if n.get("text") == "写点什么，或加一张图。"]
    if not blocks:
        assert len(empty) == 1
        assert not any(n.get("content-desc", "").startswith(("note-text-", "note-image-")) for n in observed)
        return
    assert not empty
    texts = [r for r in blocks if r[3] == "TEXT" and r[4]]
    assert texts, "selected fixture has no visible text identity witness"
    witness = texts[0]; key, text = "note-text-"+witness[1], witness[4]
    assert {r[0] for r in data["blocks"] if r[3] == "TEXT" and r[1] == witness[1] and r[4] == text} == {note}, "body witness not unique across notes"
    matches = [n.get("text") for n in observed if n.get("content-desc") == key]
    assert matches == [text], "selected note body identity differs"


def editor_order_receipt(value, api, source, run, apk, owner, note, sibling):
    return isinstance(value, dict) and (
        value.get("status") == "PASS" and value.get("scope") == EDITOR_ORDER_SCOPE and
        type(value.get("api")) is int and value["api"] == api and
        value.get("commit") == source and value.get("run_id") == run and
        isinstance(apk, str) and re.fullmatch("[0-9a-f]{64}", apk) is not None and
        value.get("apk_sha256") == apk and
        value.get("labels") == EDITOR_ORDER_LABELS and type(value.get("checks")) is int and
        value["checks"] == 6 and value.get("release_ready") is False and
        type(value.get("owner")) is int and value["owner"] == owner and owner > 0 and
        isinstance(note, str) and bool(note.strip()) and isinstance(sibling, str) and bool(sibling.strip()) and
        note != sibling and value.get("note_id") == note and value.get("sibling_id") == sibling and
        value.get("state") == "BROWSING_CANCEL_SELECTION_ALL_TABLES_REVISION_MEDIA_UNCHANGED")


def editor_order_sample():
    return {"status": "PASS", "scope": EDITOR_ORDER_SCOPE, "api": 26,
            "commit": "source", "run_id": "run", "apk_sha256": "a"*64,
            "labels": EDITOR_ORDER_LABELS[:], "checks": 6, "release_ready": False,
            "owner": 1, "note_id": "b", "sibling_id": "a",
            "state": "BROWSING_CANCEL_SELECTION_ALL_TABLES_REVISION_MEDIA_UNCHANGED"}


def editor_order_selftest():
    rows = [("first", 1, "First"), ("empty", 1, "Same"), ("filled", 1, "Same")]
    data = {"notes": rows + [("other", 2, "Other")],
            "blocks": [("first", "t1", 0, "TEXT", "First body", None, "", 0, None),
                       ("filled", "t2", 0, "TEXT", "Unique body", None, "", 0, None),
                       ("filled", "im", 1, "IMAGE", "", "asset", "", 0, None),
                       ("other", "t2", 0, "TEXT", "Wrong owner", None, "", 0, None)]}
    labels = ["1. First", "2. Same", "3. Same"]
    editor_picker_check(rows, labels)
    picker_bad = [[], labels[::-1], labels[:-1], labels + ["4. Other"],
                  ["1. First", "2. Same", "2. Same"], ["1. First", "2. Wrong", "3. Same"]]
    for bad in picker_bad:
        try: editor_picker_check(rows, bad)
        except AssertionError: pass
        else: raise AssertionError("editor picker negative survived")
    empty = [{"content-desc": "note-current", "text": "Same · 2 / 3"},
             {"text": "写点什么，或加一张图。"}]
    filled = [{"content-desc": "note-current", "text": "Same · 3 / 3"},
              {"content-desc": "note-text-t2", "text": "Unique body"}]
    editor_selection_check(data, 1, "empty", empty)
    editor_selection_check(data, 1, "filled", filled)
    bads = [("empty", filled), ("filled", empty),
            ("filled", [dict(filled[0])]), ("empty", [dict(empty[0])])]
    for note, good in (("empty", empty), ("filled", filled)):
        for key, value in (("text", "Same · 1 / 3"), ("content-desc", "wrong")):
            bad = copy.deepcopy(good); bad[0][key] = value; bads.append((note, bad))
        bads.append((note, good + [dict(good[0])]))
    bads.extend([
        ("filled", [filled[0], {"content-desc": "note-text-t2", "text": "Wrong owner"}]),
        ("filled", [filled[0], {"content-desc": "note-text-wrong", "text": "Unique body"}]),
        ("filled", filled + [dict(filled[1])]),
        ("empty", empty + [{"content-desc": "note-image-im", "text": ""}]),
        ("filled", filled + [{"text": "写点什么，或加一张图。"}]),
    ])
    for note, bad in bads:
        try: editor_selection_check(data, 1, note, bad)
        except AssertionError: pass
        else: raise AssertionError("editor selected-note negative survived")
    ambiguous = copy.deepcopy(data)
    ambiguous["blocks"].append(("empty", "t2", 0, "TEXT", "Unique body", None, "", 0, None))
    try: editor_selection_check(ambiguous, 1, "filled", filled)
    except AssertionError: pass
    else: raise AssertionError("ambiguous selected-note witness accepted")
    good = editor_order_sample()
    assert editor_order_receipt(good, 26, "source", "run", "a"*64, 1, "b", "a")
    bad_receipts = [None, {}]
    for key in good:
        bad = copy.deepcopy(good); del bad[key]; bad_receipts.append(bad)
    for key, value in (("status", "FAIL"), ("scope", "HOST_ONLY"), ("api", True),
                       ("api", 34), ("commit", "old"), ("run_id", "old"),
                       ("apk_sha256", "b"*64), ("checks", True), ("checks", 5),
                       ("owner", True), ("owner", 2), ("note_id", "a"), ("sibling_id", "b"),
                       ("release_ready", 0), ("labels", EDITOR_ORDER_LABELS[::-1]),
                       ("state", "NOT_VERIFIED")):
        bad = copy.deepcopy(good); bad[key] = value; bad_receipts.append(bad)
    for index in range(6):
        bad = copy.deepcopy(good); bad["labels"].pop(index); bad["checks"] -= 1; bad_receipts.append(bad)
    for bad in bad_receipts:
        assert not editor_order_receipt(bad, 26, "source", "run", "a"*64, 1, "b", "a")
    parent = order_ui_sample()
    for bad in bad_receipts:
        invalid = copy.deepcopy(parent); invalid["editor_ui"] = bad
        assert not order_ui_receipt(invalid, 26, "source", "run", "a"*64)
    import inspect
    mutants = [
        (editor_picker_check, "actual == expected", "True",
         lambda f: f(rows, labels[::-1])),
        (editor_selection_check, 'headers == [expected_header]', "True",
         lambda f: f(data, 1, "filled", [dict(filled[0], text="Same · 2 / 3"), filled[1]])),
        (editor_selection_check, 'matches == [text]', "True",
         lambda f: f(data, 1, "filled", [filled[0], dict(filled[1], text="Wrong owner")])),
        (editor_order_receipt, 'value.get("apk_sha256") == apk', "True", None),
    ]
    for fn, old, new, call in mutants:
        source = inspect.getsource(fn); assert source.count(old) == 1
        namespace = dict(globals()); exec(source.replace(old, new), namespace)
        mutated = namespace[fn.__name__]
        if call is not None: call(mutated)
        else:
            assert mutated(dict(good, apk_sha256="b"*64), 26, "source", "run", "a"*64, 1, "b", "a")
    print("EDITOR_ORDER_HOST picker=1_positive_"+str(len(picker_bad))+
          "_negative selection=2_positive_"+str(len(bads)+1)+
          "_negative receipt=1_positive_"+str(len(bad_receipts))+
          "_negative parent="+str(len(bad_receipts))+
          "_negative 4_mutations_exposed HOST_ONLY", flush=True)


def order_expected(before, note, owner, direction):
    assert type(owner) is int and owner > 0 and type(direction) is int and direction in (-1, 1)
    expected = copy.deepcopy(before)
    rows = expected[0]["notes"]
    assert all(len(row) == 3 for row in rows) and len({row[0] for row in rows}) == len(rows)
    slots = [i for i, row in enumerate(rows) if row[1] == owner]
    ids = [rows[i][0] for i in slots]
    assert note in ids
    at = ids.index(note); to = at + direction
    assert 0 <= to < len(slots)
    rows[slots[at]], rows[slots[to]] = rows[slots[to]], rows[slots[at]]
    revision = expected[0]["revision"]
    assert len(revision) == 1 and revision[0][0] == 1 and type(revision[0][1]) is int
    assert revision[0][1] < 9223372036854775807
    expected[0]["revision"] = [(1, revision[0][1] + 1)]
    return expected


def order_readback(before, actual, note, owner, direction):
    assert actual == order_expected(before, note, owner, direction), "order changed wrong IDs, owner slots, revision, tables or media"


def order_ui_receipt(value, api, source, run, apk):
    return isinstance(value, dict) and (
        editor_order_receipt(value.get("editor_ui"), api, source, run, apk,
                             value.get("owner"), value.get("note_id"), value.get("sibling_id")) and
        value.get("status") == "PASS" and value.get("scope") == ORDER_UI_SCOPE and
        type(value.get("api")) is int and value["api"] == api and
        value.get("commit") == source and value.get("run_id") == run and
        isinstance(apk, str) and re.fullmatch("[0-9a-f]{64}", apk) is not None and value.get("apk_sha256") == apk and
        value.get("labels") == ORDER_UI_LABELS and type(value.get("checks")) is int and
        value["checks"] == 8 and value.get("release_ready") is False and
        type(value.get("owner")) is int and value["owner"] > 0 and
        isinstance(value.get("note_id"), str) and bool(value["note_id"].strip()) and
        isinstance(value.get("sibling_id"), str) and bool(value["sibling_id"].strip()) and
        value["note_id"] != value["sibling_id"] and
        value.get("state") == "EXACT_OWNER_SLOT_SWAP_PER_MOVE_TWO_REVISIONS_ALL_OTHER_TABLES_MEDIA_UNCHANGED")


def order_ui_sample():
    return {"status": "PASS", "scope": ORDER_UI_SCOPE, "api": 26, "commit": "source", "run_id": "run",
            "editor_ui": editor_order_sample(),
            "apk_sha256": "a"*64, "labels": ORDER_UI_LABELS[:], "checks": 8, "release_ready": False,
            "owner": 1, "note_id": "b", "sibling_id": "a",
            "state": "EXACT_OWNER_SLOT_SWAP_PER_MOVE_TWO_REVISIONS_ALL_OTHER_TABLES_MEDIA_UNCHANGED"}


def order_ui_selftest():
    before = ({"notes": [("a", 1, "Same"), ("x", 2, "Other"),
                         ("b", 1, "Same"), ("c", 1, "Empty")],
               "revision": [(1, 10)], "blocks": [("a", "image", "private")],
               "field_notes": [("b", 3)], "media": [("asset", 8)]},
              {"asset": "digest"}, {1: "Owner", 2: "Other"})
    expected = copy.deepcopy(before)
    expected[0]["notes"] = [("b", 1, "Same"), ("x", 2, "Other"),
                             ("a", 1, "Same"), ("c", 1, "Empty")]
    expected[0]["revision"] = [(1, 11)]
    assert order_expected(before, "b", 1, -1) == expected
    order_readback(before, expected, "b", 1, -1)
    restored = copy.deepcopy(before); restored[0]["revision"] = [(1, 12)]
    assert order_expected(expected, "b", 1, 1) == restored
    bads = [copy.deepcopy(before)]
    for table in expected[0]:
        bad = copy.deepcopy(expected); bad[0][table] = []; bads.append(bad)
    for table, value in (("revision", [(1, 12)]),
                          ("notes", [("b", 1, "Same"), ("a", 1, "Same"), ("x", 2, "Other"), ("c", 1, "Empty")])):
        bad = copy.deepcopy(expected); bad[0][table] = value; bads.append(bad)
    for side in (1, 2):
        bad = copy.deepcopy(expected); bad[side].clear(); bads.append(bad)
    for bad in bads:
        try: order_readback(before, bad, "b", 1, -1)
        except AssertionError: pass
        else: raise AssertionError("order readback negative survived")
    for note, owner, direction in (("a", 1, -1), ("c", 1, 1), ("b", 2, -1),
                                   ("missing", 1, 1), ("b", True, 1), ("b", 1, True), ("b", 1, 0)):
        try: order_expected(before, note, owner, direction)
        except AssertionError: pass
        else: raise AssertionError("order identity or boundary negative survived")
    sample = order_ui_sample()
    assert order_ui_receipt(sample, 26, "source", "run", "a"*64)
    invalid = [None, {}]
    for key in sample:
        bad = copy.deepcopy(sample); del bad[key]; invalid.append(bad)
    for key, value in (("status", "FAIL"), ("api", True), ("api", 34),
                       ("commit", "old"), ("run_id", "old"), ("apk_sha256", "b"*64),
                       ("checks", True), ("labels", ORDER_UI_LABELS[::-1]),
                       ("scope", "HOST_ONLY"), ("owner", True), ("note_id", ""),
                       ("sibling_id", "b"), ("release_ready", True), ("state", "NOT_VERIFIED")):
        bad = copy.deepcopy(sample); bad[key] = value; invalid.append(bad)
    for index in range(len(ORDER_UI_LABELS)):
        bad = copy.deepcopy(sample); bad["labels"].pop(index); bad["checks"] -= 1; invalid.append(bad)
    for bad in invalid:
        assert not order_ui_receipt(bad, 26, "source", "run", "a"*64)
    import inspect
    for function, mutations in (
        (order_expected, [("revision[0][1] + 1", "revision[0][1] + 2"),
                          ("if row[1] == owner", "if True")]),
        (order_ui_receipt, [("value.get(\"labels\") == ORDER_UI_LABELS", "True"),
                            ("value.get(\"apk_sha256\") == apk", "True")])):
        source = inspect.getsource(function)
        for old, new in mutations:
            assert source.count(old) == 1
            namespace = dict(globals())
            exec(source.replace(old, new), namespace)
            if function is order_expected:
                assert namespace["order_expected"](before, "b", 1, -1) != expected
            else:
                assert any(namespace["order_ui_receipt"](bad, 26, "source", "run", "a"*64) for bad in invalid)
    print("ORDER_UI_HOST readback=2_positive_"+str(len(bads)+7)+
          "_negative receipt=1_positive_"+str(len(invalid))+"_negative 4_mutations_exposed HOST_ONLY", flush=True)


def deletion_expected(before, note, owner):
    expected = copy.deepcopy(before)
    data = expected[0]
    targets = [row for row in data["notes"] if row[0] == note and row[1] == owner]
    assert len(targets) == 1 and len(targets[0]) == 3, "delete target identity"
    assert sum(row[0] == note for row in data["notes"]) == 1
    for table in ("field_notes", "blocks", "notes"):
        data[table] = [row for row in data[table] if row[0] != note]
    rev = data["revision"]
    assert len(rev) == 1 and rev[0][0] == 1 and type(rev[0][1]) is int
    assert rev[0][1] < 9223372036854775807
    data["revision"] = [(1, rev[0][1]+1)]
    return expected


def deletion_readback_check(before, actual, note, owner):
    assert actual == deletion_expected(before, note, owner), "delete changed wrong note, order, revision, fields or media"


def deletion_ui_receipt(value, api, source, run, apk):
    return isinstance(value, dict) and (
        value.get("status") == "PASS" and value.get("scope") == DELETE_UI_SCOPE and
        type(value.get("api")) is int and value["api"] == api and
        value.get("commit") == source and value.get("run_id") == run and
        isinstance(apk, str) and re.fullmatch("[0-9a-f]{64}", apk) is not None and
        value.get("apk_sha256") == apk and value.get("labels") == DELETE_UI_LABELS and
        type(value.get("checks")) is int and value["checks"] == len(DELETE_UI_LABELS) and
        value.get("release_ready") is False and
        isinstance(value.get("note_id"), str) and bool(value["note_id"]) and
        isinstance(value.get("sibling_id"), str) and bool(value["sibling_id"]) and
        value["note_id"] != value["sibling_id"] and
        type(value.get("owner")) is int and value["owner"] > 0 and
        type(value.get("deleted_blocks")) is int and value["deleted_blocks"] > 0 and
        value.get("state") == "EXACT_TARGET_ROWS_ONE_REVISION_ALL_MEDIA_PRESERVED")


def deletion_ui_sample():
    return {"status": "PASS", "scope": DELETE_UI_SCOPE, "api": 26, "commit": "source",
            "run_id": "run", "apk_sha256": "a"*64, "labels": DELETE_UI_LABELS[:],
            "checks": len(DELETE_UI_LABELS), "release_ready": False,
            "note_id": "b", "sibling_id": "a", "owner": 1, "deleted_blocks": 2,
            "state": "EXACT_TARGET_ROWS_ONE_REVISION_ALL_MEDIA_PRESERVED"}


def deletion_ui_selftest():
    before = ({"notes": [("a", 1, "Same"), ("b", 1, "Same"), ("c", 2, "Same")],
        "blocks": [("a", "image", 0, "IMAGE", None, "asset", "", 0, None),
                   ("b", "image", 0, "IMAGE", None, "asset", "", 0, None),
                   ("b", "private", 1, "TEXT", "PRIVATE", None, "", 1, None)],
        "field_notes": [("b", 8), ("c", 8)], "fields": [(8, "LONG_TEXT")],
        "field_values": [(8, 1, "keep")], "revision": [(1, 9)], "media": [("asset",)]},
        {"asset": "bytes"}, {1: "First", 2: "Second"})
    good = ({"notes": [("a", 1, "Same"), ("c", 2, "Same")],
        "blocks": [("a", "image", 0, "IMAGE", None, "asset", "", 0, None)],
        "field_notes": [("c", 8)], "fields": [(8, "LONG_TEXT")],
        "field_values": [(8, 1, "keep")], "revision": [(1, 10)], "media": [("asset",)]},
        {"asset": "bytes"}, {1: "First", 2: "Second"})
    deletion_readback_check(before, good, "b", 1)
    bads = [copy.deepcopy(before)]
    for table in good[0]:
        bad = copy.deepcopy(good); bad[0][table] = []; bads.append(bad)
    bad = copy.deepcopy(good); bad[1].clear(); bads.append(bad)
    bad = copy.deepcopy(good); bad[2][1] = "Changed"; bads.append(bad)
    bad = copy.deepcopy(good); bad[0]["notes"].reverse(); bads.append(bad)
    bad = copy.deepcopy(good); bad[0]["revision"] = [(1, 11)]; bads.append(bad)
    for bad in bads:
        try: deletion_readback_check(before, bad, "b", 1)
        except AssertionError: continue
        raise AssertionError("delete readback negative survived")
    for note, owner in (("missing", 1), ("b", 2)):
        try: deletion_expected(before, note, owner)
        except AssertionError: continue
        raise AssertionError("delete wrong identity accepted")
    receipt_good = deletion_ui_sample()
    assert deletion_ui_receipt(receipt_good, 26, "source", "run", "a"*64)
    invalid = [None, {}]
    for key in receipt_good:
        bad = copy.deepcopy(receipt_good); del bad[key]; invalid.append(bad)
    for key, value in (("status", "FAIL"), ("api", True), ("api", 34), ("commit", "old"),
            ("run_id", "old"), ("apk_sha256", "b"*64), ("labels", DELETE_UI_LABELS[::-1]),
            ("checks", True), ("scope", "HOST_ONLY"), ("release_ready", True),
            ("note_id", ""), ("sibling_id", "b"), ("owner", True), ("owner", 0),
            ("deleted_blocks", True), ("deleted_blocks", 0), ("state", "NOT_VERIFIED")):
        bad = copy.deepcopy(receipt_good); bad[key] = value; invalid.append(bad)
    for index in range(len(DELETE_UI_LABELS)):
        bad = copy.deepcopy(receipt_good); bad["labels"].pop(index); bad["checks"] -= 1; invalid.append(bad)
    for bad in invalid:
        assert not deletion_ui_receipt(bad, 26, "source", "run", "a"*64), "delete receipt negative survived"
    print("DELETE_UI_HOST_CONTROLS readback=1_positive_"+str(len(bads)+2)+
          "_negative receipt=1_positive_"+str(len(invalid))+"_negative HOST_ONLY", flush=True)


def rename_expected(before, note, owner, title):
    expected = copy.deepcopy(before)
    rows = expected[0]["notes"]
    indexes = [i for i, row in enumerate(rows) if row[0] == note and row[1] == owner]
    assert len(indexes) == 1 and isinstance(title, str) and title.strip()
    index = indexes[0]
    assert len(rows[index]) == 3 and expected[0]["revision"][0][0] == 1
    if title != rows[index][2]:
        rows[index] = (note, owner, title)
        rev = expected[0]["revision"]
        assert len(rev) == 1 and type(rev[0][1]) is int and rev[0][1] < 9223372036854775807
        rev[0] = (1, rev[0][1]+1)
    return expected


def rename_readback_check(before, actual, note, owner, title):
    assert actual == rename_expected(before, note, owner, title), "rename changed wrong note, order, revision, content or media"


def rename_selftest():
    before = ({"notes": [("a", 1, "Same"), ("b", 1, "Same"), ("c", 2, "Same")],
               "revision": [(1, 9)], "blocks": [("b", "t", "private")]},
              {"asset": "bytes"}, {1: "First", 2: "Second"})
    good = copy.deepcopy(before)
    good[0]["notes"][1] = ("b", 1, "Renamed")
    good[0]["revision"] = [(1, 10)]
    rename_readback_check(before, good, "b", 1, "Renamed")
    rename_readback_check(before, copy.deepcopy(before), "b", 1, "Same")
    reverted = copy.deepcopy(before); reverted[0]["revision"] = [(1, 11)]
    rename_readback_check(good, reverted, "b", 1, "Same")
    bads = [copy.deepcopy(before)]
    for mode in range(8):
        bad = copy.deepcopy(good)
        if mode == 0: bad[0]["notes"][0] = ("a", 1, "Renamed")
        if mode == 1: bad[0]["notes"][2] = ("c", 2, "Renamed")
        if mode == 2: bad[0]["notes"].reverse()
        if mode == 3: bad[0]["notes"][1] = ("b", 2, "Renamed")
        if mode == 4: bad[0]["revision"] = [(1, 11)]
        if mode == 5: bad[0]["blocks"] = []
        if mode == 6: bad[1]["asset"] = "changed"
        if mode == 7: bad[2][1] = "changed"
        bads.append(bad)
    for bad in bads:
        try: rename_readback_check(before, bad, "b", 1, "Renamed")
        except AssertionError: continue
        raise AssertionError("rename negative survived")
    print("RENAME_HOST_CONTROLS 3_positive_9_negative HOST_ONLY", flush=True)


def summary_expected(data, owner):
    notes = [r for r in data["notes"] if r[1] == owner]
    result = {"note-count-"+str(owner): "笔记 · "+str(len(notes))+" 篇"}
    trim = "".join(chr(i) for i in range(33))
    for index, note in enumerate(notes):
        blocks = sorted((r for r in data["blocks"] if r[0] == note[0]), key=lambda r: r[2])
        texts = [r[4].strip(trim) for r in blocks if r[7] == 0 and r[3] == "TEXT" and r[4].strip(trim)]
        if texts:
            preview = texts[0][:80] + ("…" if len(texts[0]) > 80 else "")
        elif any(r[7] == 0 and r[3] == "IMAGE" for r in blocks):
            preview = "图片笔记"
        else:
            preview = "私有内容（摘要已隐藏）" if any(r[7] == 1 for r in blocks) else "空笔记"
        result["note-title-"+note[0]] = str(index+1)+". "+note[2]
        result["note-activity-"+str(owner) if index == 0 else "note-summary-"+note[0]] = preview
    return result


def summary_ui_check(expected, actual, order):
    assert actual == expected, "summary UI missing, extra, private, wrong-owner or wrong-text row"
    assert order == [key for key in expected if key.startswith("note-title-")], "summary display order differs"


def summary_selftest():
    data = {"notes": [("n1", 1, "Same"), ("n2", 1, "Same"), ("n3", 2, "Other")],
            "blocks": [("n1", "t", 0, "TEXT", "PRIVATE", None, "", 1, None),
                       ("n1", "u", 1, "TEXT", "Public", None, "", 0, None),
                       ("n3", "v", 0, "TEXT", "OTHER_OWNER", None, "", 0, None)]}
    expected = {"note-count-1": "笔记 · 2 篇", "note-title-n1": "1. Same",
                "note-activity-1": "Public", "note-title-n2": "2. Same", "note-summary-n2": "空笔记"}
    assert summary_expected(data, 1) == expected
    assert summary_expected(data, 99) == {"note-count-99": "笔记 · 0 篇"}
    summary_ui_check(expected, dict(expected), ["note-title-n1", "note-title-n2"])
    bads = []
    for key in expected:
        bad = dict(expected); del bad[key]; bads.append((bad, ["note-title-n1", "note-title-n2"]))
    for key, value in (("note-activity-1", "PRIVATE"), ("note-summary-n2", "OTHER_OWNER"),
                       ("note-count-1", "笔记 · 1 篇"), ("note-title-n2", "1. Same"),
                       ("note-summary-n3", "OTHER_OWNER")):
        bad = dict(expected); bad[key] = value; bads.append((bad, ["note-title-n1", "note-title-n2"]))
    bads.append((dict(expected), ["note-title-n2", "note-title-n1"]))
    for actual, order in bads:
        try: summary_ui_check(expected, actual, order)
        except AssertionError: continue
        raise AssertionError("summary UI negative survived")
    hidden = copy.deepcopy(data); hidden["blocks"][1] = ("n1", "u", 1, "TEXT", "Public", None, "", 1, None)
    assert summary_expected(hidden, 1)["note-activity-1"] == "私有内容（摘要已隐藏）"
    print("SUMMARY_UI_HOST_CONTROLS projection=3 observer=1_positive_11_negative HOST_ONLY", flush=True)


def markdown_check(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert z.namelist() == ["notes.md"], "batch ZIP membership"
        assert z.getinfo("notes.md").file_size == len(EXPECTED.encode())
        assert z.read("notes.md").decode("utf-8") == EXPECTED, "batch text/order/privacy"


def pdf_text_check(text):
    assert "".join(text.split()) == "SecondeditedBatchsecond", "batch PDF text/order/privacy"


def cancel_readback_check(before_paths, after_paths, filename, baseline, actual):
    # Download directory membership, not arbitrary-provider atomicity or file-content proof.
    assert "/sdcard/Download/"+filename not in before_paths, "cancel target already exists"
    assert after_paths == before_paths, "cancel changed Download file membership"
    assert actual == baseline, "cancel changed database or private media"


def privacy_readback_check(baseline, actual, note, block):
    rows = baseline[0]["blocks"]
    matches = [i for i, row in enumerate(rows) if row[0] == note and row[1] == block]
    assert len(matches) == 1, "privacy target must be one exact composite identity"
    index = matches[0]
    assert len(rows[index]) == 9 and rows[index][3] == "TEXT" and rows[index][7] == 0
    expected = copy.deepcopy(baseline)
    changed = list(rows[index]); changed[7] = 1
    expected[0]["blocks"][index] = tuple(changed)
    assert actual == expected, "privacy injection changed more than target flag or bumped revision"


def stale_output_check(paths, filename, raw):
    assert (paths == [] and raw is None) or (
        paths == ["/sdcard/Download/"+filename] and type(raw) is bytes and raw == b""
    ), "stale batch output must be absent or exactly empty"


def receipt(value, api, source, run, apk):
    if not isinstance(value, dict):
        return False
    if not order_ui_receipt(value.get("order_ui"), api, source, run, apk):
        return False
    if not note_management.accepted(value.get("note_management"), api, source, run, apk):
        return False
    if not deletion_ui_receipt(value.get("deletion_ui"), api, source, run, apk):
        return False
    if not (value.get("status") == "PASS" and value.get("scope") == SCOPE and
            type(value.get("api")) is int and value["api"] == api and
            value.get("commit") == source and value.get("run_id") == run and
            isinstance(apk, str) and re.fullmatch("[0-9a-f]{64}", apk) and
            value.get("apk_sha256") == apk and value.get("labels") == LABELS and
            type(value.get("checks")) is int and value["checks"] == len(LABELS) and
            value.get("release_ready") is False):
        return False
    summary = value.get("summary_ui")
    rename = value.get("rename_ui")
    if not isinstance(rename, dict) or not (
            rename.get("status") == "PASS" and rename.get("labels") == RENAME_LABELS and
            type(rename.get("checks")) is int and rename["checks"] == len(RENAME_LABELS) and
            type(rename.get("api")) is int and rename["api"] == api and
            rename.get("commit") == source and rename.get("run_id") == run and
            rename.get("apk_sha256") == apk and rename.get("release_ready") is False and
            rename.get("scope") == "NATIVE_NOTE_RENAME_EXACT_ID_RESTART_NOT_LMK"):
        return False
    if not isinstance(summary, dict) or not (
            summary.get("status") == "PASS" and summary.get("labels") == SUMMARY_LABELS and
            type(summary.get("checks")) is int and summary["checks"] == len(SUMMARY_LABELS) and
            type(summary.get("api")) is int and summary["api"] == api and
            summary.get("commit") == source and summary.get("run_id") == run and
            summary.get("apk_sha256") == apk and summary.get("release_ready") is False and
            summary.get("scope") == "NATIVE_ACTIVITY_SUMMARIES_SYNTHETIC_RESTART_NOT_LMK"):
        return False
    outputs = value.get("outputs")
    if not isinstance(outputs, dict) or set(outputs) != {x[0] for x in FORMATS}:
        return False
    stale = value.get("stale_privacy")
    if not isinstance(stale, dict) or set(stale) != {x[0] for x in FORMATS}:
        return False
    for kind, _, _ in FORMATS:
        proof = stale[kind]
        if not isinstance(proof, dict) or not (
                isinstance(proof.get("note_id"), str) and proof["note_id"] and
                isinstance(proof.get("block_id"), str) and proof["block_id"] and
                isinstance(proof.get("helper_sha256"), str) and re.fullmatch("[0-9a-f]{64}", proof["helper_sha256"]) and
                proof.get("scope") == "SAME_REVISION_SECOND_NOTE_ONE_PRIVATE_FLAG" and
                proof.get("publication") in ("EMPTY", "ABSENT") and
                type(proof.get("published_bytes")) is int and proof["published_bytes"] == 0 and
                proof.get("state") == "EXACT_CHANGED_STATE_THEN_EXACT_BASELINE_RESTORED"):
            return False
        o = outputs[kind]
        if not isinstance(o, dict):
            return False
        if not (type(o.get("bytes")) is int and 0 < o["bytes"] <= 16777216 and
                isinstance(o.get("sha256"), str) and re.fullmatch("[0-9a-f]{64}", o["sha256"]) and
                o.get("state") == "ALL_TABLES_AND_ALL_MEDIA_UNCHANGED" and
                o.get("observer") == ("EXACT_MEMBERS_UTF8" if kind == "MARKDOWN" else
                                     "EXACT_PDF_TEXT" if kind == "PDF" else "TWO_TEXT_BANDS_NOT_OCR")):
            return False
    return True


PAGE_CHECK = r'''
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;
import java.io.File;
public class BatchPageCheck {
 static void check(BufferedImage p) {
  if(p==null||p.getWidth()!=595||p.getHeight()!=842)throw new AssertionError("dimensions");
  boolean[] rows=new boolean[842];
  for(int y=0;y<842;y++)for(int x=0;x<595;x++){
   int v=p.getRGB(x,y);
   if(v!=0xffffffff){
    if((v>>>24)!=255||x<36||x>=260||y<36||y>=130)throw new AssertionError("outside text region");
    rows[y]=true;
   }
  }
  int bands=0;boolean before=false;
  for(boolean row:rows){if(row&&!before)bands++;before=row;}
  if(bands!=2)throw new AssertionError("exactly two text bands");
 }
 static BufferedImage blank(){
  BufferedImage p=new BufferedImage(595,842,2);
  for(int y=0;y<842;y++)for(int x=0;x<595;x++)p.setRGB(x,y,0xffffffff);
  return p;
 }
 public static void main(String[] args)throws Exception{
  if(args[0].equals("--selftest")){
   BufferedImage good=blank();good.setRGB(40,42,0xff000000);good.setRGB(40,82,0xff000000);check(good);
   for(int mode=0;mode<5;mode++){
    BufferedImage bad=blank();
    if(mode>0)bad.setRGB(40,42,0xff000000);
    if(mode>1)bad.setRGB(40,82,0xff000000);
    if(mode==2)bad.setRGB(40,102,0xff000000);
    if(mode==3)bad.setRGB(300,200,0xff000000);
    if(mode==4)bad.setRGB(40,42,0x80000000);
    try{check(bad);}catch(AssertionError expected){continue;}
    throw new AssertionError("negative pixel control survived "+mode);
   }
   System.out.println("BATCH_PAGE_CONTROLS 1 positive 5 negatives");return;
  }
  check(ImageIO.read(new File(args[0])));System.out.println("BATCH_PAGE_PASS");
 }
}
'''


def scan_batch_summaries(read_nodes, swipe, expected, package, records,
                         viewport_for, gesture_for):
    """25 observations, at most 24 useful gestures; never retry wrong content.

    Bounds describe observed UI geometry, not Android touch/scroll physics.
    The caller owns records before entry so failures cannot discard them.
    """
    actual, order, frames = {}, [], []
    previous = None
    for attempt in range(25):
        record = {"attempt": attempt, "status": "READING"}
        records.append(record)
        try:
            current = list(read_nodes())
            signature = hashlib.sha256(json.dumps(
                [sorted(n.attrib.items()) for n in current],
                ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
            record.update(frame_sha256=signature,
                          changed_from_previous=None if previous is None else signature != previous)
            previous = signature
            viewport = viewport_for(current, package)
            record["viewport"] = list(viewport)
            frame, seen = [], set()
            record["rows"] = frame
            for node in current:
                key = node.get("content-desc", "")
                if not key.startswith(("note-count-", "note-title-", "note-activity-", "note-summary-")):
                    continue
                value = node.get("text", "")
                frame.append({"id": key, "text": value, "bounds": node.get("bounds")})
                assert key not in seen, "duplicate summary identity in frame"
                seen.add(key)
                assert node.get("package") == package, "summary belongs to another package"
                match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
                assert match, "summary has malformed bounds"
                x1, y1, x2, y2 = map(int, match.groups())
                left, top, right, bottom = viewport
                assert left <= x1 < x2 <= right and top <= y1 < y2 <= bottom, "summary outside observed viewport"
                assert key in expected, "unexpected summary identity"
                assert value == expected[key], "summary text differs"
                assert key not in actual or actual[key] == value, "summary changed while scrolling"
                if key.startswith("note-title-") and key not in actual:
                    order.append(key)
                actual[key] = value
            frames.append(frame)
            record["missing"] = sorted(set(expected) - set(actual))
            if set(expected) <= set(actual):
                summary_ui_check(expected, actual, order)
                record["status"] = "EXACT_SUMMARIES_FOUND"
                return frames
            if attempt < 24:
                coordinates = gesture_for(viewport)
                record.update(gesture=list(coordinates), duration_ms=350, status="SWIPE_REQUESTED")
                swipe(*coordinates)
            else:
                record["status"] = "ABSENT_AT_BOUND"
        except Exception as exc:
            record.update(status="FAILED", error=repr(exc))
            raise
    raise AssertionError("summary rows unreachable: " + repr(set(expected) - set(actual)))


def batch_scroll_selftest():
    # Run the actual scanner and shared geometry, not an alternative implementation.
    import inspect
    import ast
    # Importing emulator_gate changes cwd and requires Android runner variables.
    # Compile only its two pure geometry functions for this host-only control.
    geometry_source = Path(__file__).with_name("emulator_gate.py").read_text()
    geometry_tree = ast.parse(geometry_source)
    names = {"summary_viewport", "summary_gesture"}
    functions = [node for node in geometry_tree.body
                 if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(functions) == 2 and {node.name for node in functions} == names
    geometry = {"re": re}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "<actual-shared-geometry>", "exec"), geometry)
    summary_viewport, summary_gesture = geometry["summary_viewport"], geometry["summary_gesture"]
    package = "test.package"
    viewport = (18, 293, 302, 578)
    expected = {"note-count-1": "笔记 · 2 篇", "note-title-a": "1. Same",
                "note-activity-1": "Public", "note-title-b": "2. Same",
                "note-summary-b": "空笔记"}

    def bounds(box):
        return "[%d,%d][%d,%d]" % box

    def frame(keys, box=viewport):
        left, top, right, bottom = box
        nodes = [ET.Element("node", {"content-desc": "activity-details-scroll",
                 "package": package, "class": "android.widget.ScrollView",
                 "enabled": "true", "bounds": bounds(box)})]
        for key in keys:
            nodes.append(ET.Element("node", {"content-desc": key, "text": expected[key],
                         "package": package, "bounds": bounds((left, top+1, right, top+2))}))
        return nodes

    def exercise(fn, frames, want_failure=None, want_swipes=None):
        receipts, gestures, observations = [], [], []
        def read():
            at = len(observations)
            result = frames[min(at, len(frames)-1)]
            observations.append(result)
            return result
        def swipe(x1, y1, x2, y2):
            left, top, right, bottom = summary_viewport(observations[-1], package)
            assert left < x1 == x2 < right and top < y2 < y1 < bottom, "gesture outside viewport"
            assert (x1, y1, x2, y2) == summary_gesture((left, top, right, bottom)), "gesture is not half viewport"
            gestures.append((x1, y1, x2, y2))
        try:
            result = fn(read, swipe, expected, package, receipts, summary_viewport, summary_gesture)
        except AssertionError as exc:
            assert want_failure is not None and want_failure in str(exc), (want_failure, str(exc))
            result = None
        else:
            assert want_failure is None, "negative accepted: "+str(want_failure)
        assert len(receipts) == len(observations), "missing frame receipt"
        for i, record in enumerate(receipts):
            assert record["attempt"] == i
            assert re.fullmatch("[0-9a-f]{64}", record["frame_sha256"])
            assert record["changed_from_previous"] is (None if i == 0 else
                record["frame_sha256"] != receipts[i-1]["frame_sha256"])
        if want_swipes is not None:
            assert len(gestures) == want_swipes, "gesture budget changed"
        if want_failure is None:
            assert receipts[-1]["status"] == "EXACT_SUMMARIES_FOUND"
            assert receipts[-1]["missing"] == []
            assert result and all(isinstance(f, list) for f in result)
        elif want_failure == "summary rows unreachable":
            assert len(receipts) == 25 and receipts[-1]["status"] == "ABSENT_AT_BOUND"
            assert receipts[-1]["missing"] == sorted(expected)
        else:
            assert receipts[-1]["status"] == "FAILED" and receipts[-1]["error"]
        for record, gesture in zip(receipts, gestures):
            assert record["gesture"] == list(gesture), "missing gesture receipt"
            assert record["duration_ms"] == 350
        return receipts

    all_keys = list(expected)
    exercise(scan_batch_summaries, [frame(all_keys)], want_swipes=0)
    # Changed viewport on the second observation: never reuse stale geometry.
    shifted = (31, 117, 391, 617)
    exercise(scan_batch_summaries, [frame(all_keys[:2]), frame(all_keys[2:4], shifted),
                                   frame(all_keys[4:], shifted)], want_swipes=2)
    for box in ((18, 293, 302, 578), (18, 281, 302, 578), (0, 0, 1080, 1920), (1, 1, 5, 5)):
        exercise(scan_batch_summaries, [frame([], box), frame(all_keys, box)], want_swipes=1)
    exercise(scan_batch_summaries, [frame([])]*24+[frame(all_keys)], want_swipes=24)
    exercise(scan_batch_summaries, [frame([])], "summary rows unreachable", 24)
    negatives = []
    for key, value, message in (
        ("package", "other", "another package"), ("class", "wrong", "invalid summary viewport"),
        ("enabled", "false", "invalid summary viewport"), ("bounds", "bad", "malformed bounds"),
        ("bounds", "[18,293][18,578]", "too small"),
        ("bounds", "[-1,293][302,578]", "malformed bounds")):
        bad = frame(all_keys); bad[0].set(key, value); negatives.append((bad, message))
    negatives.extend([(frame(all_keys)[1:], "missing or duplicate"),
                      (frame(all_keys)+[frame([])[0]], "missing or duplicate")])
    for key, value, message in (
        ("package", "other", "another package"), ("text", "PRIVATE", "summary text differs"),
        ("content-desc", "note-summary-other-owner", "unexpected summary identity"),
        ("bounds", "bad", "malformed bounds"),
        ("bounds", "[18,292][302,300]", "outside observed viewport"),
        ("bounds", "[18,300][18,310]", "outside observed viewport")):
        bad = frame(all_keys); bad[1].set(key, value); negatives.append((bad, message))
    negatives.append((frame(all_keys)+[frame(all_keys)[1]], "duplicate summary identity"))
    negatives.append((frame([all_keys[0], all_keys[3], all_keys[4], all_keys[1], all_keys[2]]),
                      "summary display order differs"))
    for bad, message in negatives:
        exercise(scan_batch_summaries, [bad], message, 0)
    # Wrong content must fail now, not wait until all other expected rows are found.
    partial = frame([all_keys[0]]); partial[1].set("text", "wrong")
    exercise(scan_batch_summaries, [partial], "summary text differs", 0)
    # Exceptions from transport are preserved, not retried; incomplete receipt remains reachable.
    sentinel = OSError("transport sentinel")
    receipts = []
    def broken(): raise sentinel
    try:
        scan_batch_summaries(broken, None, expected, package, receipts, summary_viewport, summary_gesture)
    except OSError as exc:
        assert exc is sentinel and len(receipts) == 1 and receipts[0]["status"] == "FAILED"
    else:
        raise AssertionError("transport failure swallowed")
    # Demonstrate each mutant preserves an ordinary fully-visible case, then is killed
    # by the same checker used above. This is not a replay of original touch physics.
    original = inspect.getsource(scan_batch_summaries)
    mutants = [
        ("coordinates = gesture_for(viewport)", "coordinates = (160, 440, 160, 190)",
         [frame([]), frame(all_keys)], None, 1),
        ("range(25)", "range(24)", [frame([])]*24+[frame(all_keys)], None, 24),
        ("gesture=list(coordinates)", "gesture=[]", [frame([]), frame(all_keys)], None, 1),
        ("assert value == expected[key]", "assert True", [partial], "summary text differs", 0),
        ('assert key not in seen, "duplicate summary identity in frame"',
         'assert True, "duplicate summary identity in frame"',
         [frame(all_keys)+[frame(all_keys)[1]]], "duplicate summary identity", 0),
        ("summary_ui_check(expected, actual, order)", "pass",
         [negatives[-1][0]], "summary display order differs", 0),
    ]
    for old, new, frames, failure, swipes in mutants:
        assert original.count(old) == 1, "mutation anchor drift"
        namespace = dict(globals()); exec(original.replace(old, new), namespace)
        mutated = namespace["scan_batch_summaries"]
        exercise(mutated, [frame(all_keys)], want_swipes=0)
        try:
            exercise(mutated, frames, failure, swipes)
        except AssertionError:
            pass
        else:
            raise AssertionError("batch scroll mutant survived: "+old)
    print("BATCH_SCROLL_HOST positive=7 negative="+str(len(negatives)+3)+
          " witnessed_mutants="+str(len(mutants))+" HOST_ONLY_NOT_ANDROID_PHYSICS", flush=True)


def batch_scroll_wiring_selftest():
    import ast
    import inspect
    def check(source):
        tree = ast.parse(source)
        native_node = tree.body[0]
        summary = next(n for n in native_node.body if isinstance(n, ast.FunctionDef) and n.name == "summary_ui")
        observe = next(n for n in summary.body if isinstance(n, ast.FunctionDef) and n.name == "observe")
        required = ast.parse(
            'navigation = {"label": label, "owner": owner, "frames": []}\n'
            'proof.setdefault("navigation", []).append(navigation)\n'
            'def bounded_swipe(x1, y1, x2, y2):\n'
            '    shell("input", "swipe", str(x1), str(y1), str(x2), str(y2), "350")\n'
            'frames = scan_batch_summaries(nodes, bounded_swipe, expected, gate.PKG, '
            'navigation["frames"], gate.summary_viewport, gate.summary_gesture)\n').body
        wanted = [ast.dump(n) for n in required]
        actual = [ast.dump(n) for n in observe.body]
        assert sum(actual[i:i+len(wanted)] == wanted for i in range(len(actual))) == 1, "batch navigation wiring missing"
        # The caller may no longer contain its old fixed-coordinate scan loop.
        assert not any(isinstance(n, ast.For) for n in observe.body
                       if any(isinstance(a, ast.Constant) and a.value == 25 for a in ast.walk(n))), "old scanner retained"
    source = inspect.getsource(native)
    check(source)
    mutants = [
        ('proof.setdefault("navigation", []).append(navigation)', 'pass'),
        ('navigation["frames"],', '[],'),
        ('gate.summary_gesture)', 'gate.wrong_gesture)'),
    ]
    for old, new in mutants:
        assert source.count(old) == 1, "wiring mutation anchor drift"
        try:
            check(source.replace(old, new))
        except AssertionError as exc:
            assert str(exc) == "batch navigation wiring missing"
        else:
            raise AssertionError("batch navigation wiring mutation survived")
    print("BATCH_SCROLL_WIRING positive=1 negative=3 ACTUAL_NATIVE_AST_NOT_DEVICE", flush=True)


def selftest():
    batch_scroll_selftest()
    batch_scroll_wiring_selftest()
    note_management.selftest()
    editor_order_selftest()
    order_ui_selftest()
    deletion_ui_selftest()
    rename_selftest()
    summary_selftest()
    assert len(LABELS) == 34 and all("picker_cancel_preserves_state_"+kind in LABELS
                                   for kind in ("MARKDOWN", "PDF", "PNG_ZIP"))
    assert all(step+"_"+kind in LABELS for kind in ("MARKDOWN", "PDF", "PNG_ZIP")
               for step in ("same_revision_second_note_privacy", "stale_publication_refused",
                            "stale_refusal_preserves_state", "privacy_fixture_restored"))
    # Composite identity matters: both notes deliberately use the same block ID.
    row = ("second", "shared", 0, "TEXT", "chosen", None, "", 0, None)
    other = ("first", "shared", 0, "TEXT", "other", None, "", 0, None)
    original = ({"blocks": [other, row], "revision": [(1, 9)], "notes": [("first",), ("second",)]},
                {"asset": "digest"}, {1: "owner"})
    changed = copy.deepcopy(original)
    changed[0]["blocks"][1] = row[:7]+(1,)+row[8:]
    privacy_readback_check(original, changed, "second", "shared")
    bad_privacy = [copy.deepcopy(original)]
    for mode in range(6):
        bad = copy.deepcopy(changed)
        if mode == 0: bad[0]["revision"] = [(1, 10)]
        if mode == 1: bad[0]["blocks"][0] = other[:7]+(1,)+other[8:]
        if mode == 2: bad[0]["blocks"].reverse()
        if mode == 3: bad[1]["asset"] = "changed"
        if mode == 4: bad[0]["notes"].pop()
        if mode == 5: bad[0]["blocks"][1] = row[:4]+("leaked change",)+row[5:7]+(1,)+row[8:]
        bad_privacy.append(bad)
    actions = [lambda bad=bad: privacy_readback_check(original, bad, "second", "shared")
               for bad in bad_privacy]
    actions.append(lambda: privacy_readback_check(original, changed, "missing", "shared"))
    actions.append(lambda: privacy_readback_check(original, changed, "first", "shared"))
    duplicate = copy.deepcopy(original); duplicate[0]["blocks"].append(row)
    actions.append(lambda: privacy_readback_check(duplicate, changed, "second", "shared"))
    for action in actions:
        try: action()
        except AssertionError: continue
        raise AssertionError("privacy negative survived")
    stale_output_check([], "new.zip", None)
    stale_output_check(["/sdcard/Download/new.zip"], "new.zip", b"")
    stale_bad = [
        (["/sdcard/Download/new.zip"], b"private"),
        (["/sdcard/Download/new.zip"], None),
        (["/sdcard/Download/wrong.zip"], b""),
        (["/sdcard/Download/new.zip", "/sdcard/Download/extra.zip"], b""),
        ([], b"private"), (["/sdcard/Download/new.zip"], ""),
    ]
    for paths, raw in stale_bad:
        try: stale_output_check(paths, "new.zip", raw)
        except AssertionError: continue
        raise AssertionError("stale output negative survived")
    paths = ["/sdcard/Download/existing.zip"]
    baseline = ({"notes": [(1, "public")], "meta": [(9,)]}, {"asset": "digest"}, {1: "title"})
    cancel_readback_check(paths, paths[:], "new.zip", baseline, copy.deepcopy(baseline))
    changed_db = copy.deepcopy(baseline); changed_db[0]["notes"] = [(1, "private")]
    changed_revision = copy.deepcopy(baseline); changed_revision[0]["meta"] = [(10,)]
    changed_media = copy.deepcopy(baseline); changed_media[1]["asset"] = "different"
    cancel_bad = [
        (paths, paths, "existing.zip", baseline),
        (paths, paths+["/sdcard/Download/new.zip"], "new.zip", baseline),
        (paths, [], "new.zip", baseline),
        (paths, paths+["/sdcard/Download/unexpected.zip"], "new.zip", baseline),
        (paths, paths, "new.zip", changed_db),
        (paths, paths, "new.zip", changed_revision),
        (paths, paths, "new.zip", changed_media),
    ]
    for before, after, filename, actual in cancel_bad:
        try:
            cancel_readback_check(before, after, filename, baseline, actual)
        except AssertionError:
            continue
        raise AssertionError("batch cancellation negative survived")
    # The format button starts abbreviated, but preview/status use full titles.
    # These explicit expectations are independent of the product constant.
    assert FORMATS == (("MARKDOWN", "Markdown图片包", "PocketTodo-notes.zip"),
                       ("PDF", "PDF", "PocketTodo-notes.pdf"),
                       ("PNG_ZIP", "分段PNG图片包", "PocketTodo-pages.zip"))
    assert [title+"预览" for _, title, _ in FORMATS] == [
        "Markdown图片包预览", "PDF预览", "分段PNG图片包预览"]
    assert [title+"已保存，逐字节回读一致" for _, title, _ in FORMATS] == [
        "Markdown图片包已保存，逐字节回读一致", "PDF已保存，逐字节回读一致",
        "分段PNG图片包已保存，逐字节回读一致"]
    def archive(text, extra=False):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            z.writestr("notes.md", text)
            if extra:
                z.writestr("assets/original.png", b"forbidden")
        return out.getvalue()
    markdown_check(archive(EXPECTED))
    pdf_text_check("Second edited\n\nBatchsecond\n\f")
    negatives = [
        lambda: markdown_check(archive(EXPECTED, True)),
        lambda: markdown_check(archive(EXPECTED.replace("Second edited\n\nBatchsecond", "Batchsecond\n\nSecond edited"))),
        lambda: markdown_check(archive(EXPECTED + "PRIVATE_SHARE_SENTINEL")),
        lambda: markdown_check(archive(EXPECTED.replace("Batchsecond\n\n", ""))),
        lambda: pdf_text_check("Batchsecond Second edited"),
        lambda: pdf_text_check("Second edited"),
        lambda: pdf_text_check("Second edited Batchsecond Batchunselected"),
    ]
    for action in negatives:
        try:
            action()
        except AssertionError:
            continue
        raise AssertionError("batch output negative survived")
    good = {"status": "PASS", "scope": SCOPE, "api": 26, "commit": "source", "run_id": "run",
            "apk_sha256": "a"*64, "labels": LABELS[:], "checks": len(LABELS),
            "release_ready": False, "outputs": {}, "stale_privacy": {}}
    good["note_management"] = note_management.sample()
    good["deletion_ui"] = deletion_ui_sample()
    good["order_ui"] = order_ui_sample()
    good["summary_ui"] = {"status": "PASS", "labels": SUMMARY_LABELS[:], "checks": len(SUMMARY_LABELS),
        "api": 26, "commit": "source", "run_id": "run", "apk_sha256": "a"*64,
        "scope": "NATIVE_ACTIVITY_SUMMARIES_SYNTHETIC_RESTART_NOT_LMK", "release_ready": False}
    good["rename_ui"] = {"status": "PASS", "labels": RENAME_LABELS[:], "checks": len(RENAME_LABELS),
        "api": 26, "commit": "source", "run_id": "run", "apk_sha256": "a"*64,
        "scope": "NATIVE_NOTE_RENAME_EXACT_ID_RESTART_NOT_LMK", "release_ready": False}
    for kind, _, _ in FORMATS:
        good["stale_privacy"][kind] = {
            "note_id": "second", "block_id": "selected", "helper_sha256": "c"*64,
            "scope": "SAME_REVISION_SECOND_NOTE_ONE_PRIVATE_FLAG",
            "publication": "EMPTY", "published_bytes": 0,
            "state": "EXACT_CHANGED_STATE_THEN_EXACT_BASELINE_RESTORED"}
        good["outputs"][kind] = {"bytes": 100, "sha256": "b"*64,
            "state": "ALL_TABLES_AND_ALL_MEDIA_UNCHANGED",
            "observer": "EXACT_MEMBERS_UTF8" if kind == "MARKDOWN" else
                        "EXACT_PDF_TEXT" if kind == "PDF" else "TWO_TEXT_BANDS_NOT_OCR"}
    assert receipt(good, 26, "source", "run", "a"*64)
    bads = [None, {}, dict(good, status="FAIL"), dict(good, api=True), dict(good, api=34),
            dict(good, commit="old"), dict(good, run_id="old"), dict(good, apk_sha256="c"*64),
            dict(good, checks=True), dict(good, release_ready=True), dict(good, scope="backend")]
    bads.extend([dict(good, stale_privacy=None), dict(good, stale_privacy={})])
    bads.extend([dict(good, summary_ui=None), dict(good, summary_ui={})])
    bads.extend([dict(good, rename_ui=None), dict(good, rename_ui={})])
    bads.extend([dict(good, note_management=None), dict(good, note_management={})])
    bads.extend([dict(good, deletion_ui=None), dict(good, deletion_ui={})])
    bads.extend([dict(good, order_ui=None), dict(good, order_ui={})])
    for key, value in (("status", "FAIL"), ("checks", True), ("api", 34), ("api", True),
                       ("commit", "old"), ("run_id", "old"), ("apk_sha256", "d"*64),
                       ("scope", "HOST_ONLY"), ("release_ready", True)):
        b = copy.deepcopy(good); b["rename_ui"][key] = value; bads.append(b)
    for index in range(len(RENAME_LABELS)):
        b = copy.deepcopy(good); b["rename_ui"]["labels"].pop(index)
        b["rename_ui"]["checks"] -= 1; bads.append(b)
    for key, value in (("status", "FAIL"), ("checks", True), ("api", 34), ("api", True),
                       ("commit", "old"), ("run_id", "old"), ("apk_sha256", "d"*64),
                       ("scope", "HOST_ONLY"), ("release_ready", True)):
        b = copy.deepcopy(good); b["summary_ui"][key] = value; bads.append(b)
    for index in range(len(SUMMARY_LABELS)):
        b = copy.deepcopy(good); b["summary_ui"]["labels"].pop(index)
        b["summary_ui"]["checks"] -= 1; bads.append(b)
    for i in range(len(LABELS)):
        b = copy.deepcopy(good); b["labels"].pop(i); b["checks"] -= 1; bads.append(b)
    for kind, _, _ in FORMATS:
        b = copy.deepcopy(good); del b["stale_privacy"][kind]; bads.append(b)
        for key, value in (("note_id", ""), ("block_id", None), ("helper_sha256", "bad"),
                           ("scope", "SINGLE_NOTE"), ("publication", "NONEMPTY"),
                           ("published_bytes", True), ("published_bytes", 1), ("state", "NOT_VERIFIED")):
            b = copy.deepcopy(good); b["stale_privacy"][kind][key] = value; bads.append(b)
        b = copy.deepcopy(good); del b["outputs"][kind]; bads.append(b)
        for key, value in (("bytes", True), ("bytes", 0), ("sha256", "bad"),
                           ("state", "NOT_VERIFIED"), ("observer", "NONBLANK")):
            b = copy.deepcopy(good); b["outputs"][kind][key] = value; bads.append(b)
    for b in bads:
        assert not receipt(b, 26, "source", "run", "a"*64), "batch incomplete receipt accepted"
    # Execute the real composition, not a source substring check.
    from types import SimpleNamespace
    global native
    actual_native = native
    events = []
    try:
        native = lambda adb, gate: events.append(("batch", adb))
        gate = SimpleNamespace(verify_native_ui=lambda adb: events.append(("old", adb)))
        install(gate); gate.verify_native_ui("device")
        assert events == [("old", "device"), ("batch", "device")]
        sentinel = RuntimeError("old suite failed")
        def failed(adb): raise sentinel
        gate = SimpleNamespace(verify_native_ui=failed); install(gate)
        try: gate.verify_native_ui("device")
        except RuntimeError as exc: assert exc is sentinel
        else: raise AssertionError("old suite failure swallowed")
        assert events == [("old", "device"), ("batch", "device")]
    finally:
        native = actual_native
    print("BATCH_HOST_CONTROLS outputs=2_positive_7_negative receipts=1_positive_" +
          str(len(bads)) + "_negative composition=2 format_contracts=3 cancel=1_positive_7_negative "
          "privacy=1_positive_10_negative stale=2_positive_6_negative HOST_ONLY", flush=True)


def native(adb, gate):
    """Fixtures originate in visible UI. A verified external helper changes one
    privacy flag at the same revision while DocumentsUI holds a reviewed ticket."""
    from verify_paged_exports import format_button
    from verify_process_control import stop_verified
    from verify_schema3 import cancel_share_picker
    source, run_id = os.environ["GITHUB_SHA"], os.environ["GITHUB_RUN_ID"]
    out = Path("native-ui"); prefix = [str(adb), "-s", gate.SERIAL]; serial = 0
    result = {"status": "FAIL", "scope": SCOPE, "commit": source, "run_id": run_id,
              "api": gate.API, "labels": [], "checks": 0, "outputs": {}, "release_ready": False}
    def command(*args, binary=False):
        return subprocess.check_output(prefix + list(args), text=not binary, stderr=subprocess.PIPE,
                                       stdin=subprocess.DEVNULL, timeout=40)
    def shell(*args): return command("shell", "-n", "-T", *args)
    def nodes():
        shell("uiautomator", "dump", "/sdcard/batch-window.xml")
        return list(ET.fromstring(shell("cat", "/sdcard/batch-window.xml")).iter("node"))
    def find(**attrs):
        deadline = time.monotonic() + 20; current = []
        while time.monotonic() < deadline:
            current = nodes()
            found = [n for n in current if all(n.get(k) == v for k, v in attrs.items())]
            assert len(found) <= 1, "ambiguous batch control " + repr(attrs)
            if found: return found[0]
            time.sleep(.25)
        raise AssertionError("batch control missing " + repr(attrs) + " actual=" + repr([n.attrib for n in current]))
    def click(n):
        assert n.get("enabled") == "true"
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", n.get("bounds")))
        assert x2 > x1 and y2 > y1
        shell("input", "tap", str((x1+x2)//2), str((y1+y2)//2))
    def tap(text): click(find(text=text))
    def touch(desc): click(find(**{"content-desc": desc}))
    def ready(): find(**{"content-desc": "v12-status", "text": "已保存到本机"})
    def stop(): stop_verified(adb, gate.SERIAL, gate.PKG)
    def start():
        shell("am", "start", "-W", "-n", gate.PKG + "/com.supercubegame.pockettodo.MainActivity"); ready()
    def state():
        nonlocal serial
        serial += 1; local = out / ("batch-state-" + str(serial) + ".db")
        local.write_bytes(command("exec-out", "run-as", gate.PKG, "cat", "databases/pocket-v12.db", binary=True))
        if "pocket-v12.db-wal" in shell("run-as", gate.PKG, "ls", "databases").splitlines():
            Path(str(local)+"-wal").write_bytes(command("exec-out", "run-as", gate.PKG, "cat", "databases/pocket-v12.db-wal", binary=True))
        with sqlite3.connect(local) as db:
            tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            data = {t: db.execute('SELECT * FROM "'+t+'" ORDER BY rowid').fetchall() for t in tables}
            titles = dict(db.execute("SELECT id,title FROM activities"))
        media = {}
        for name in shell("run-as", gate.PKG, "ls", "files/media").splitlines():
            assert re.fullmatch("[0-9a-f]{64}", name)
            raw = command("exec-out", "run-as", gate.PKG, "cat", "files/media/"+name, binary=True)
            media[name] = hashlib.sha256(raw).hexdigest(); assert media[name] == name
        return data, media, titles
    def ok(label):
        assert LABELS[len(result["labels"])] == label, "batch obligation order"
        result["labels"].append(label)
    def checked():
        return [n for n in nodes() if n.get("class") == "android.widget.CheckedTextView"]
    def open_notes():
        tap("导出笔记"); tap("批量选择"); find(text="勾选笔记（下一步逐项选择内容）")
        assert checked() and all(n.get("checked") == "false" for n in checked())
    def select_notes():
        # Deliberately reverse click order. The output must retain document order.
        tap(note_labels[1]); tap(note_labels[0]); tap("选择内容")
        find(text="勾选内容（私有项已排除）")
        c = checked()
        assert [n.get("text") for n in c] == block_labels
        assert all(n.get("checked") == "false" for n in c)
    def consent():
        for _ in range(8):
            c = [n for n in nodes() if n.get("text") == "我已核对内容与图片，可保存此包"]
            if c:
                assert len(c) == 1 and c[0].get("checked") == "false"
                click(c[0]); return
            shell("input", "swipe", "160", "440", "160", "190", "350")
        raise AssertionError("batch consent unreachable")
    def downloads():
        return sorted(shell("find", "/sdcard/Download", "-type", "f").splitlines())
    def external_privacy(value, previous):
        remote = "/data/user/0/"+gate.PKG+"/cache/share-writer.jar"
        helper = command("exec-out", "run-as", gate.PKG, "cat", remote, binary=True)
        digest = hashlib.sha256(helper).hexdigest()
        assert digest == prior["markdown_ui"]["external_helper"]["sha256"]
        output = shell("run-as", gate.PKG, "env", "CLASSPATH="+remote, "app_process",
                       "/system/bin", "ShareExternalWriter",
                       "/data/user/0/"+gate.PKG+"/databases/pocket-v12.db",
                       second, privacy_target[1], str(value), str(previous))
        assert output.splitlines() == ["EXTERNAL_WRITER_STARTED", "EXTERNAL_PRIVACY_WRITE_ONE_ROW"], output
        return digest
    def preserve_output(tag, filename):
        paths = shell("find", "/sdcard/Download", "-type", "f", "-name", filename).splitlines()
        if paths:
            assert paths == ["/sdcard/Download/"+filename]
            destination = "/sdcard/Download/batch-"+tag+"-"+filename
            assert destination not in downloads()
            shell("mv", paths[0], destination)
        assert not shell("find", "/sdcard/Download", "-type", "f", "-name", filename).splitlines()
    def summary_ui():
        # Reuse existing real-UI-created fixtures; no second APK, DB injection or suite rerun.
        proof = {"status": "FAIL", "api": gate.API, "commit": source, "run_id": run_id,
                 "apk_sha256": result["apk_sha256"], "labels": [], "screens": [],
                 "scope": "NATIVE_ACTIVITY_SUMMARIES_SYNTHETIC_RESTART_NOT_LMK", "release_ready": False}
        result["summary_ui"] = proof
        first_owner = next(r[1] for r in data["notes"] if r[0] == first)
        second_owner = second_rows[0][1]
        first_notes = [r for r in data["notes"] if r[1] == first_owner]
        assert first_owner != second_owner and len(first_notes) >= 3
        assert len({r[2] for r in first_notes}) < len(first_notes), "same-title fixture required"
        assert any(not any(b[0] == n[0] for b in data["blocks"]) for n in first_notes), "empty fixture required"
        def passed(label):
            assert SUMMARY_LABELS[len(proof["labels"])] == label
            proof["labels"].append(label)
        def swipe():
            shell("input", "swipe", "160", "440", "160", "190", "350")
        def observe(owner, snapshot, label):
            start(); tap("活动"); ready()
            # Locate an exact stable activity identity, scrolling rather than matching titles.
            for _ in range(20):
                visible = [n for n in nodes() if n.get("content-desc") == "activity-"+str(owner)]
                assert len(visible) <= 1
                if visible:
                    click(visible[0]); ready(); break
                swipe()
            else: raise AssertionError("summary fixture activity unreachable")
            expected = summary_expected(snapshot[0], owner)
            navigation = {"label": label, "owner": owner, "frames": []}
            proof.setdefault("navigation", []).append(navigation)
            def bounded_swipe(x1, y1, x2, y2):
                shell("input", "swipe", str(x1), str(y1), str(x2), str(y2), "350")
            frames = scan_batch_summaries(
                nodes, bounded_swipe, expected, gate.PKG, navigation["frames"],
                gate.summary_viewport, gate.summary_gesture)
            file = out/("summary-"+label+".png")
            file.write_bytes(command("exec-out", "screencap", "-p", binary=True))
            proof["screens"].append({"label": label, "owner": owner, "frames": frames,
                                     "screenshot": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()})
            stop(); assert state() == snapshot, "summary browsing mutated database or media"
            passed(label)
        stop(); assert state() == baseline
        observe(first_owner, baseline, "all_same_title_and_empty_notes")
        observe(second_owner, baseline, "second_activity_isolated")
        observe(first_owner, baseline, "restart_all_notes")
        observe(second_owner, baseline, "restart_second_activity")
        external_privacy(1, 0); changed = state()
        privacy_readback_check(baseline, changed, second, privacy_target[1])
        assert summary_expected(baseline[0], second_owner)["note-activity-"+str(second_owner)] == "Batchsecond"
        assert summary_expected(changed[0], second_owner)["note-activity-"+str(second_owner)] == "Batchunselected"
        passed("same_revision_privacy")
        observe(second_owner, changed, "newly_private_text_hidden")
        external_privacy(0, 1); assert state() == baseline; passed("privacy_fixture_restored")
        assert command("exec-out", "cat", installed[8:], binary=True) == product
        assert state() == baseline; passed("all_tables_media_unchanged")
        assert proof["labels"] == SUMMARY_LABELS and len(proof["screens"]) == 5
        proof.update(status="PASS", checks=len(proof["labels"]))
    def rename_ui():
        # Real dialogs on the second of two same-title notes, not injected SQL edits.
        proof = {"status": "FAIL", "api": gate.API, "commit": source, "run_id": run_id,
                 "apk_sha256": result["apk_sha256"], "labels": [], "checks": 0,
                 "scope": "NATIVE_NOTE_RENAME_EXACT_ID_RESTART_NOT_LMK", "release_ready": False}
        result["rename_ui"] = proof
        pairs = [(a, b) for i, a in enumerate(data["notes"]) for b in data["notes"][i+1:]
                 if a[1] == b[1] and a[2] == b[2]]
        assert pairs, "same-title rename fixture missing"
        sibling, target = pairs[0]
        note, owner, original = target
        proof.update(note_id=note, sibling_id=sibling[0], owner=owner)
        def passed(label):
            assert RENAME_LABELS[len(proof["labels"])] == label
            proof["labels"].append(label); proof["checks"] = len(proof["labels"])
        def locate(desc):
            for _ in range(25):
                found = [n for n in nodes() if n.get("content-desc") == desc]
                assert len(found) <= 1
                if found:
                    assert found[0].get("package") == gate.PKG
                    return found[0]
                shell("input", "swipe", "160", "440", "160", "190", "350")
            raise AssertionError("rename identity unreachable "+desc)
        def form(expected):
            start(); tap("活动"); ready()
            click(locate("activity-"+str(owner))); ready()
            heading = locate("note-title-"+note)
            index = [r[0] for r in data["notes"] if r[1] == owner].index(note)
            assert heading.get("text") == str(index+1)+". "+expected
            click(heading); find(text="笔记改名")
            field = find(**{"content-desc": "note-rename-title"})
            assert field.get("text") == expected
            click(field); shell("input", "keyevent", "KEYCODE_MOVE_END")
        stop(); assert state() == baseline
        form(original); shell("input", "text", "_cancel"); tap("取消")
        stop(); assert state() == baseline; passed("cancel_readonly")
        form(original)
        # Delete UTF-16 units from the prefilled field; no clipboard/IME Unicode injection.
        units = len(original.encode("utf-16-le"))//2
        assert 0 < units <= 200, "fixture title outside bounded input driver"
        shell("input", "keyevent", *(["KEYCODE_DEL"]*units))
        assert find(**{"content-desc": "note-rename-title"}).get("text") == ""
        tap("保存标题"); find(text="笔记标题不能为空"); find(text="笔记改名"); tap("取消")
        stop(); assert state() == baseline; passed("blank_blocked_readonly")
        form(original); tap("保存标题"); ready()
        stop(); assert state() == baseline; passed("same_title_noop")
        changed_title = original+"_renamed"
        form(original); shell("input", "text", "_renamed"); tap("保存标题"); ready()
        stop(); saved = state()
        rename_readback_check(baseline, saved, note, owner, changed_title)
        passed("same_title_target_only")
        form(changed_title); tap("取消"); stop()
        assert state() == saved; passed("restart_title_persisted")
        form(changed_title)
        shell("input", "keyevent", *(["KEYCODE_DEL"]*len("_renamed")))
        assert find(**{"content-desc": "note-rename-title"}).get("text") == original
        tap("保存标题"); ready(); stop()
        restored = state()
        rename_readback_check(saved, restored, note, owner, original)
        assert [r for r in restored[0]["notes"] if r[0] in (note, sibling[0])] == [sibling, target]
        passed("duplicate_title_allowed")
        assert proof["labels"] == RENAME_LABELS
        proof.update(status="PASS", state="ONLY_TARGET_TITLE_AND_TWO_REVISION_INCREMENTS_TITLE_RESTORED")
    def order_ui():
        # Only existing visible-UI-created synthetic notes. Never seed the live DB.
        stop(); initial = state()
        pairs = [(a, b) for i, a in enumerate(initial[0]["notes"]) for b in initial[0]["notes"][i+1:]
                 if a[1:] == b[1:]]
        assert pairs, "same-title order fixture missing"
        sibling, target = pairs[0]; note, owner, title = target
        owner_rows = [r for r in initial[0]["notes"] if r[1] == owner]
        assert owner_rows.index(target) > 0 and owner_rows[owner_rows.index(target)-1] == sibling, "adjacent same-title order fixture required"
        proof = {"status": "FAIL", "scope": ORDER_UI_SCOPE, "api": gate.API, "commit": source,
                 "run_id": run_id, "apk_sha256": result["apk_sha256"], "labels": [], "checks": 0,
                 "release_ready": False, "note_id": note, "sibling_id": sibling[0], "owner": owner}
        result["order_ui"] = proof
        def passed(label):
            assert ORDER_UI_LABELS[len(proof["labels"])] == label
            proof["labels"].append(label); proof["checks"] = len(proof["labels"])
        def locate(desc):
            for _ in range(25):
                found = [n for n in nodes() if n.get("content-desc") == desc]
                assert len(found) <= 1, "duplicate order control " + desc
                if found:
                    assert found[0].get("package") == gate.PKG
                    return found[0]
                shell("input", "swipe", "160", "440", "160", "190", "350")
            raise AssertionError("order control unreachable " + desc)
        def detail(activity):
            start(); tap("活动"); ready()
            click(locate("activity-"+str(activity))); ready()
        def observe(snapshot, activity):
            detail(activity)
            rows = [r for r in snapshot[0]["notes"] if r[1] == activity]
            expected = summary_expected(snapshot[0], activity)
            buttons = {prefix+r[0]: "true" if enabled else "false"
                       for i, r in enumerate(rows) for prefix, enabled in
                       (("note-up-", i > 0), ("note-down-", i < len(rows)-1))}
            actual, order, controls = {}, [], {}
            for _ in range(25):
                for n in nodes():
                    key = n.get("content-desc", "")
                    if key in expected:
                        assert n.get("package") == gate.PKG
                        text = n.get("text", "")
                        assert key not in actual or actual[key] == text
                        if key.startswith("note-title-") and key not in actual: order.append(key)
                        actual[key] = text
                    if key in buttons:
                        assert n.get("package") == gate.PKG and n.get("class") == "android.widget.Button"
                        assert n.get("enabled") == buttons[key], "wrong order boundary " + key
                        controls[key] = n.get("enabled")
                if set(expected) <= set(actual) and set(buttons) <= set(controls):
                    summary_ui_check(expected, actual, order); break
                shell("input", "swipe", "160", "440", "160", "190", "350")
            else: raise AssertionError("order summary/control coverage incomplete")
            stop(); assert state() == snapshot, "order browsing wrote database or media"
        editor_proof = {"status": "FAIL", "scope": EDITOR_ORDER_SCOPE, "api": gate.API,
                        "commit": source, "run_id": run_id, "apk_sha256": result["apk_sha256"],
                        "labels": [], "checks": 0, "release_ready": False,
                        "owner": owner, "note_id": note, "sibling_id": sibling[0]}
        proof["editor_ui"] = editor_proof
        def editor_passed(label):
            assert EDITOR_ORDER_LABELS[len(editor_proof["labels"])] == label
            editor_proof["labels"].append(label); editor_proof["checks"] = len(editor_proof["labels"])
        def editor_observe(snapshot, phase):
            rows = [r for r in snapshot[0]["notes"] if r[1] == owner]
            # Existing three-entry fixture fits a single picker viewport; do not claim pagination.
            assert len(rows) == 3 and rows[0][0] not in (note, sibling[0])
            assert not any(r[0] == note for r in snapshot[0]["blocks"])
            assert any(r[0] == sibling[0] and r[3] == "TEXT" for r in snapshot[0]["blocks"])
            detail(owner); tap("笔记"); ready()
            def selected(identity):
                find(**{"content-desc": "note-current"})
                current = nodes()
                relevant = [n for n in current if n.get("content-desc") == "note-current" or
                            n.get("content-desc", "").startswith(("note-text-", "note-image-")) or
                            n.get("text") == "写点什么，或加一张图。"]
                assert relevant and all(n.get("package") == gate.PKG for n in relevant)
                editor_selection_check(snapshot[0], owner, identity, relevant)
            def picker():
                tap("切换笔记"); find(text="选择笔记")
                items = [n for n in nodes() if n.get("resource-id") == "android:id/text1"]
                assert all(n.get("package") == gate.PKG for n in items)
                editor_picker_check(rows, [n.get("text") for n in items])
            selected(rows[0][0]); editor_passed(phase+"_fresh_default_first")
            picker(); tap("取消"); selected(rows[0][0])
            stop(); assert state() == snapshot, "editor picker cancellation mutated state"
            editor_passed(phase+"_picker_order_cancel_readonly")
            detail(owner); tap("笔记"); ready()
            for identity in (note, sibling[0]):
                picker()
                index = [r[0] for r in rows].index(identity)
                tap(str(index+1)+". "+rows[index][2]); ready(); selected(identity)
            stop(); assert state() == snapshot, "editor selection mutated state"
            editor_passed(phase+"_same_title_identity_readonly")
        observe(initial, owner); passed("boundary_controls")
        singles = [a for a in initial[2] if sum(r[1] == a for r in initial[0]["notes"]) == 1]
        assert singles, "singleton order fixture missing"
        observe(initial, singles[0]); passed("singleton_disabled_readonly")
        detail(owner); click(locate("note-up-"+note)); ready()
        stop(); moved = state(); order_readback(initial, moved, note, owner, -1)
        passed("same_title_up_exact_state")
        observe(moved, owner); passed("restart_up_summary_order")
        editor_observe(moved, "up")
        detail(owner); click(locate("note-down-"+note)); ready()
        stop(); restored = state(); order_readback(moved, restored, note, owner, 1)
        passed("same_title_down_exact_state")
        observe(restored, owner); passed("restart_down_summary_order")
        editor_observe(restored, "down")
        expected = copy.deepcopy(initial)
        expected[0]["revision"] = [(1, initial[0]["revision"][0][1]+2)]
        assert restored == expected; passed("original_order_restored_two_revisions")
        assert initial[1] and state()[1] == initial[1]; passed("all_media_preserved")
        editor_proof.update(status="PASS", state="BROWSING_CANCEL_SELECTION_ALL_TABLES_REVISION_MEDIA_UNCHANGED")
        proof.update(status="PASS", state="EXACT_OWNER_SLOT_SWAP_PER_MOVE_TWO_REVISIONS_ALL_OTHER_TABLES_MEDIA_UNCHANGED")
        assert order_ui_receipt(proof, gate.API, source, run_id, result["apk_sha256"])
    def deletion_ui():
        # Run last: only synthetic emulator fixtures, after every old suite has finished.
        # Backend field-link/shared-reference/stale-write contracts remain separate.
        proof = {"status": "FAIL", "api": gate.API, "commit": source, "run_id": run_id,
                 "apk_sha256": result["apk_sha256"], "labels": [], "checks": 0,
                 "scope": DELETE_UI_SCOPE, "release_ready": False}
        result["deletion_ui"] = proof
        stop(); initial = state()
        pairs = [(a, b) for a in initial[0]["notes"] for b in initial[0]["notes"]
                 if a[0] != b[0] and a[1:] == b[1:] and
                 any(row[0] == b[0] and row[3] == "IMAGE" for row in initial[0]["blocks"])]
        assert pairs, "same-title image-note deletion fixture missing"
        sibling, target = pairs[0]
        note, owner, title = target
        blocks = [row for row in initial[0]["blocks"] if row[0] == note]
        links = [row for row in initial[0]["field_notes"] if row[0] == note]
        assert blocks and initial[1], "nonempty note and immutable media required"
        proof.update(note_id=note, sibling_id=sibling[0], owner=owner, deleted_blocks=len(blocks),
                     deleted_field_links=len(links), preserved_media_files=len(initial[1]))
        def passed(label):
            assert DELETE_UI_LABELS[len(proof["labels"])] == label
            proof["labels"].append(label); proof["checks"] = len(proof["labels"])
        def locate(desc):
            for _ in range(25):
                found = [n for n in nodes() if n.get("content-desc") == desc]
                assert len(found) <= 1, "duplicate delete control "+desc
                if found:
                    assert found[0].get("package") == gate.PKG
                    return found[0]
                shell("input", "swipe", "160", "440", "160", "190", "350")
            raise AssertionError("delete identity unreachable "+desc)
        def detail():
            start(); tap("活动"); ready()
            click(locate("activity-"+str(owner))); ready()
        def preview():
            detail(); click(locate("note-delete-"+note)); find(text="确认删除笔记？")
            identity = find(**{"content-desc": "note-delete-identity"})
            assert identity.get("text") == "活动："+initial[2][owner]+"\n笔记："+title+"\n笔记标识："+note
            counts = find(**{"content-desc": "note-delete-counts"})
            assert counts.get("text") == "将删除 "+str(len(blocks))+" 个正文块、"+str(len(links))+" 个字段笔记关联。\n字段和值、其他笔记和图片文件均保留。"
            consent = locate("note-delete-consent")
            assert consent.get("checked") == "false" and consent.get("enabled") == "true"
            assert consent.get("text") == "我明白只删除这一篇，且无法撤销"
            return consent
        preview(); passed("preview_exact_identity_counts")
        tap("取消"); stop(); assert state() == initial; passed("cancel_readonly")
        preview(); tap("确认删除")
        find(**{"content-desc": "note-delete-validation", "text": "请先勾选删除确认"})
        assert find(**{"content-desc": "note-delete-consent"}).get("checked") == "false"
        assert state() == initial; passed("unchecked_blocked_readonly")
        # Kill a checked, still-open dialog. No saved token/consent may reappear.
        touch("note-delete-consent")
        assert find(**{"content-desc": "note-delete-consent"}).get("checked") == "true"
        stop(); assert state() == initial; passed("process_loss_readonly")
        start()
        assert not any(n.get("text") == "确认删除笔记？" or
                       n.get("content-desc") == "note-delete-consent" for n in nodes())
        # start() above only establishes the post-restart root; detail() can reuse it.
        consent = preview(); passed("fresh_preview_unchecked")
        click(consent); assert find(**{"content-desc": "note-delete-consent"}).get("checked") == "true"
        tap("确认删除"); ready()
        stop(); deleted = state()
        deletion_readback_check(initial, deleted, note, owner)
        assert sibling in deleted[0]["notes"]
        passed("same_title_target_only")
        assert deleted[1] == initial[1] and deleted[0]["media"] == initial[0]["media"]
        passed("all_media_preserved")
        detail()
        expected = summary_expected(deleted[0], owner)
        actual, order = {}, []
        for _ in range(25):
            for node in nodes():
                key = node.get("content-desc", "")
                assert key not in ("note-title-"+note, "note-delete-"+note, "note-summary-"+note)
                if key.startswith(("note-count-", "note-title-", "note-activity-", "note-summary-")):
                    assert node.get("package") == gate.PKG
                    value = node.get("text", "")
                    assert key not in actual or actual[key] == value
                    if key.startswith("note-title-") and key not in actual: order.append(key)
                    actual[key] = value
            if set(expected) <= set(actual):
                summary_ui_check(expected, actual, order); break
            shell("input", "swipe", "160", "440", "160", "190", "350")
        else: raise AssertionError("surviving delete summary rows unreachable")
        stop(); assert state() == deleted; passed("restart_deletion_and_sibling_persisted")
        assert proof["labels"] == DELETE_UI_LABELS
        proof.update(status="PASS", state="EXACT_TARGET_ROWS_ONE_REVISION_ALL_MEDIA_PRESERVED")
    try:
        assert os.environ.get("GITHUB_ACTIONS") == "true" and shell("getprop", "ro.kernel.qemu").strip() == "1"
        prior = json.loads((out/"native-result.json").read_text())
        assert prior["status"] == "PASS" and prior["paged_ui"]["status"] == "PASS"
        apks = list(Path("build/outputs/apk/debug").glob("*.apk")); assert len(apks) == 1
        product = apks[0].read_bytes(); result["apk_sha256"] = hashlib.sha256(product).hexdigest()
        installed = shell("pm", "path", gate.PKG).strip()
        assert installed.startswith("package:") and "\n" not in installed
        assert command("exec-out", "cat", installed[8:], binary=True) == product
        stop(); before = state()
        derivatives = [r for r in before[0]["blocks"] if r[8] is not None]; assert len(derivatives) == 1
        first = derivatives[0][0]
        assert any(r[0] == first and r[7] == 1 and r[6] == "PRIVATE_SHARE_SENTINEL" for r in before[0]["blocks"])
        assert not any(r[2] == "Batchnote" for r in before[0]["notes"])
        start(); tap("活动"); ready()
        adds = [n for n in nodes() if n.get("content-desc", "").startswith("category-add-")]
        assert adds; click(adds[0]); touch("活动名称"); shell("input", "text", "Batchnote"); tap("保存"); ready()
        activity = find(text="Batchnote").get("content-desc"); assert re.fullmatch(r"activity-\d+", activity)
        touch(activity); ready(); tap("笔记"); ready()
        for text in ("Batchsecond", "Batchunselected"):
            tap("加入文字"); touch("文字内容"); shell("input", "text", text); tap("保存"); ready()
        stop(); baseline = state(); data, media, titles = baseline
        second_rows = [r for r in data["notes"] if r[2] == "Batchnote"]; assert len(second_rows) == 1
        second = second_rows[0][0]
        assert [r[4] for r in data["blocks"] if r[0] == second] == ["Batchsecond", "Batchunselected"]
        privacy_targets = [r for r in data["blocks"] if r[0] == second and r[3] == "TEXT" and r[4] == "Batchsecond"]
        assert len(privacy_targets) == 1 and privacy_targets[0][7] == 0
        privacy_target = privacy_targets[0]
        assert media == before[1] and len(data["notes"]) == len(before[0]["notes"]) + 1
        note_labels = [next(str(i+1)+". "+titles[r[1]]+" / "+r[2] for i, r in enumerate(data["notes"]) if r[0] == n)
                       for n in (first, second)]
        selected = [r for n in (first, second) for r in sorted(data["blocks"], key=lambda r: r[2]) if r[0] == n and r[7] == 0]
        assert len(selected) == 4 and [r[4] for r in selected if r[3] == "TEXT"] == ["Second edited", "Batchsecond", "Batchunselected"]
        owners = {r[0]: titles[r[1]]+" / "+r[2] for r in data["notes"]}
        block_labels = [str(i+1)+". ["+owners[r[0]]+"] "+("文字："+r[4] if r[3] == "TEXT" else "图片："+r[6])
                        for i, r in enumerate(selected)]
        chosen = [block_labels[i] for i, r in enumerate(selected) if r[3] == "TEXT" and r[4] in ("Second edited", "Batchsecond")]
        assert len(chosen) == 2
        ok("ui_created_second_note")
        start(); open_notes(); tap("选择内容"); find(text="勾选笔记（下一步逐项选择内容）")
        assert all(n.get("checked") == "false" for n in checked()); ok("empty_note_selection_blocked")
        tap("取消"); stop(); assert state() == baseline; ok("note_cancel_preserves_state")
        start(); open_notes(); select_notes(); tap("取消"); stop()
        assert state() == baseline; ok("content_cancel_preserves_state")
        java = out/"BatchPageCheck.java"; java.write_text(PAGE_CHECK)
        subprocess.run(["javac", "-d", str(out), str(java)], check=True, timeout=40)
        subprocess.run(["java", "-Djava.awt.headless=true", "-cp", str(out), "BatchPageCheck", "--selftest"], check=True, timeout=40)
        for kind, title, filename in FORMATS:
            old = shell("find", "/sdcard/Download", "-type", "f", "-name", filename).splitlines()
            if old:
                assert old == ["/sdcard/Download/"+filename]
                destination = "/sdcard/Download/pre-batch-"+filename
                assert not shell("find", "/sdcard/Download", "-type", "f", "-name", "pre-batch-"+filename).splitlines()
                shell("mv", old[0], destination)
            before_downloads = downloads()
            start(); open_notes(); select_notes(); ok("explicit_reverse_clicks_private_excluded_"+kind)
            tap("生成预览"); find(text="勾选内容（私有项已排除）")
            assert all(n.get("checked") == "false" for n in checked()); ok("empty_content_blocked_"+kind)
            if kind != "MARKDOWN":
                button = format_button(nodes(), "Markdown", gate.PKG); assert button is not None
                click(button); tap(title)
            tap(chosen[1]); tap(chosen[0]); tap("生成预览"); find(text=title+"预览")
            tap("选择保存位置"); find(text=title+"预览")
            assert not any("documentsui" in n.get("package", "") for n in nodes())
            ok("unchecked_save_blocked_"+kind); consent(); tap("选择保存位置")
            assert find(text=filename).get("package") in ("com.android.documentsui", "com.google.android.documentsui")
            assert find(text="SAVE").get("package") in ("com.android.documentsui", "com.google.android.documentsui")
            trace = []
            result.setdefault("cancel_traces", {})[kind] = trace
            cancel_share_picker(nodes, lambda: shell("input", "keyevent", "KEYCODE_BACK"), gate.PKG, trace)
            stop()
            cancel_readback_check(before_downloads, downloads(), filename, baseline, state())
            ok("picker_cancel_preserves_state_"+kind)
            # Cancellation consumes the old preview. Generate and consent afresh.
            start(); open_notes(); select_notes()
            if kind != "MARKDOWN":
                button = format_button(nodes(), "Markdown", gate.PKG); assert button is not None
                click(button); tap(title)
            tap(chosen[1]); tap(chosen[0]); tap("生成预览"); find(text=title+"预览")
            consent(); tap("选择保存位置")
            assert find(text=filename).get("package") in ("com.android.documentsui", "com.google.android.documentsui")
            assert find(text="SAVE").get("package") in ("com.android.documentsui", "com.google.android.documentsui")
            tap("SAVE"); find(**{"content-desc": "v12-status", "text": title+"已保存，逐字节回读一致"})
            assert shell("find", "/sdcard/Download", "-type", "f", "-name", filename).splitlines() == ["/sdcard/Download/"+filename]
            raw = command("exec-out", "cat", "/sdcard/Download/"+filename, binary=True)
            assert 0 < len(raw) <= 16777216
            artifact = out/("batch-"+filename); artifact.write_bytes(raw)
            if kind == "MARKDOWN":
                markdown_check(raw)
            elif kind == "PDF":
                info = subprocess.check_output(["pdfinfo", str(artifact)], text=True, timeout=30)
                assert re.findall(r"^Pages:\s+(\d+)", info, re.M) == ["1"]
                textfile = out/"batch-pdf.txt"
                subprocess.run(["pdftotext", "-enc", "UTF-8", str(artifact), str(textfile)], check=True, timeout=30)
                pdf_text_check(textfile.read_text())
            else:
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    assert z.namelist() == ["pages/page-001.png"]
                    assert z.getinfo("pages/page-001.png").file_size <= 16777216
                    page = out/"batch-page.png"; page.write_bytes(z.read("pages/page-001.png"))
                subprocess.run(["java", "-Djava.awt.headless=true", "-cp", str(out), "BatchPageCheck", str(page)], check=True, timeout=40)
            ok("saved_and_independently_read_"+kind)
            stop(); assert state() == baseline; ok("all_tables_media_unchanged_"+kind)
            result["outputs"][kind] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                "state": "ALL_TABLES_AND_ALL_MEDIA_UNCHANGED",
                "observer": "EXACT_MEMBERS_UTF8" if kind == "MARKDOWN" else
                            "EXACT_PDF_TEXT" if kind == "PDF" else "TWO_TEXT_BANDS_NOT_OCR"}
            preserve_output("accepted", filename)
            start(); open_notes(); select_notes()
            if kind != "MARKDOWN":
                button = format_button(nodes(), "Markdown", gate.PKG); assert button is not None
                click(button); tap(title)
            tap(chosen[1]); tap(chosen[0]); tap("生成预览"); find(text=title+"预览")
            consent(); tap("选择保存位置")
            assert find(text=filename).get("package") in ("com.android.documentsui", "com.google.android.documentsui")
            assert find(text="SAVE").get("package") in ("com.android.documentsui", "com.google.android.documentsui")
            digest = external_privacy(1, 0)
            changed = state()
            privacy_readback_check(baseline, changed, second, privacy_target[1])
            ok("same_revision_second_note_privacy_"+kind)
            tap("SAVE")
            find(**{"content-desc": "v12-status",
                    "text": "导出未完成：预览过期或保存失败；本机笔记未改。目标可能留有空文件或部分文件，请检查"})
            paths = shell("find", "/sdcard/Download", "-type", "f", "-name", filename).splitlines()
            stale = command("exec-out", "cat", paths[0], binary=True) if paths == ["/sdcard/Download/"+filename] else None
            stale_output_check(paths, filename, stale)
            ok("stale_publication_refused_"+kind)
            stop(); assert state() == changed; ok("stale_refusal_preserves_state_"+kind)
            assert external_privacy(0, 1) == digest
            assert state() == baseline; ok("privacy_fixture_restored_"+kind)
            result.setdefault("stale_privacy", {})[kind] = {
                "note_id": second, "block_id": privacy_target[1], "helper_sha256": digest,
                "scope": "SAME_REVISION_SECOND_NOTE_ONE_PRIVATE_FLAG",
                "publication": "EMPTY" if paths else "ABSENT", "published_bytes": 0,
                "state": "EXACT_CHANGED_STATE_THEN_EXACT_BASELINE_RESTORED"}
            preserve_output("stale-empty", filename)
        summary_ui()
        rename_ui()
        result["note_management"] = note_management.native(adb, gate, state)
        order_ui()
        deletion_ui()
        assert command("exec-out", "cat", installed[8:], binary=True) == product
        result.update(status="PASS", checks=len(result["labels"]))
        assert receipt(result, gate.API, source, run_id, result["apk_sha256"])
        return result
    except Exception as exc:
        from verify_schema3 import exception_evidence
        result.update(status="FAIL", error=repr(exc), original_failure=exception_evidence(exc))
        try:
            (out/"batch-failure.png").write_bytes(command("exec-out", "screencap", "-p", binary=True))
        except Exception as diagnostic:
            result["screenshot_error"] = repr(diagnostic)
        raise
    finally:
        result["checks"] = len(result["labels"])
        (out/"batch-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
        for filename in ("native-result.json", "codec-result.json"):
            path = out/filename
            parent = json.loads(path.read_text()); parent["batch_ui"] = result
            if result["status"] != "PASS": parent["status"] = "FAIL"
            path.write_text(json.dumps(parent, ensure_ascii=False, indent=2)+"\n")
        print("BATCH_NATIVE_RESULT "+json.dumps(result, ensure_ascii=False), flush=True)


def install(gate):
    previous = gate.verify_native_ui
    def previous_then_batch(adb):
        previous(adb)
        native(adb, gate)
    gate.verify_native_ui = previous_then_batch


if __name__ == "__main__":
    import sys
    assert sys.argv[1:] == ["selftest"], "usage: verify_batch_exports.py selftest"
    selftest()
