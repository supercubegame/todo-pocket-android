package com.supercubegame.pockettodo;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;

public final class TodoModel {
    public static final int MAX_ITEMS = 500;
    public static final int MAX_TITLE = 200;
    public static final class Item {
        public final long id;
        public final String title;
        public final boolean done;
        Item(long id, String title, boolean done) {
            this.id = id; this.title = title; this.done = done;
        }
    }
    private final ArrayList<Item> items = new ArrayList<>();
    private long nextId = 1;
    public List<Item> items() {
        return Collections.unmodifiableList(new ArrayList<>(items));
    }
    private static String validTitle(String title) {
        if (title == null || title.trim().isEmpty() || title.trim().length() > MAX_TITLE)
            throw new IllegalArgumentException("请输入 1 至 200 字的待办");
        return title.trim();
    }
    public long add(String title) {
        String clean = validTitle(title);
        if (items.size() >= MAX_ITEMS || nextId == Long.MAX_VALUE)
            throw new IllegalArgumentException("最多保存 500 条待办");
        long id = nextId++;
        items.add(new Item(id, clean, false));
        return id;
    }
    private int index(long id) {
        for (int i = 0; i < items.size(); i++) if (items.get(i).id == id) return i;
        throw new IllegalArgumentException("待办不存在");
    }
    public void edit(long id, String title) {
        String clean = validTitle(title);
        int i = index(id);
        Item old = items.get(i);
        items.set(i, new Item(old.id, clean, old.done));
    }
    public void toggle(long id) {
        int i = index(id);
        Item old = items.get(i);
        items.set(i, new Item(old.id, old.title, !old.done));
    }
    public void remove(long id) { items.remove(index(id)); }
    public String encode() {
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            DataOutputStream out = new DataOutputStream(bytes);
            out.writeInt(0x544F4431);
            out.writeLong(nextId);
            out.writeInt(items.size());
            for (Item item : items) {
                out.writeLong(item.id);
                out.writeUTF(item.title);
                out.writeBoolean(item.done);
            }
            out.flush();
            return Base64.getEncoder().encodeToString(bytes.toByteArray());
        } catch (IOException e) { throw new IllegalStateException(e); }
    }
    public static TodoModel decode(String encoded) {
        TodoModel model = new TodoModel();
        if (encoded == null) throw new IllegalArgumentException("本地数据无法读取，原始数据已保留");
        if (encoded.isEmpty()) return model;
        try {
            if (encoded.length() > 1000000) throw new IOException("oversize");
            DataInputStream in = new DataInputStream(new ByteArrayInputStream(Base64.getDecoder().decode(encoded)));
            if (in.readInt() != 0x544F4431) throw new IOException("version");
            model.nextId = in.readLong();
            int count = in.readInt();
            if (count < 0 || count > MAX_ITEMS || model.nextId < 1) throw new IOException("bounds");
            HashSet<Long> ids = new HashSet<>();
            for (int i = 0; i < count; i++) {
                long id = in.readLong();
                String title = in.readUTF();
                int flag = in.readUnsignedByte();
                if (id < 1 || id >= model.nextId || !ids.add(id) || flag > 1 ||
                    title.isEmpty() || !title.equals(title.trim()) || title.length() > MAX_TITLE)
                    throw new IOException("invalid item");
                model.items.add(new Item(id, title, flag == 1));
            }
            if (in.available() != 0) throw new IOException("trailing data");
            return model;
        } catch (IOException | IllegalArgumentException e) {
            throw new IllegalArgumentException("本地数据无法读取，原始数据已保留", e);
        }
    }
}
