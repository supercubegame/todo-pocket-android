import com.supercubegame.pockettodo.TodoModel;
import java.util.Base64;
import java.lang.reflect.InvocationTargetException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

public final class CoreTest {
    private static int checks = 0;
    static void check(boolean ok, String name) {
        if (!ok) throw new AssertionError(name);
        checks++;
        System.out.println("PASS " + name);
    }
    static void rejects(Runnable action, String name) {
        boolean rejected = false;
        try { action.run(); } catch (IllegalArgumentException expected) { rejected = true; }
        check(rejected, name);
    }
    static Object invoke(String cls, String method, Object target, Class<?>[] types, Object... args) {
        try { return Class.forName(cls).getMethod(method, types).invoke(target, args); }
        catch (InvocationTargetException e) {
            if (e.getCause() instanceof RuntimeException) throw (RuntimeException)e.getCause();
            throw new AssertionError(e.getCause());
        } catch (ReflectiveOperationException e) { throw new AssertionError("Required v1.1 capability missing: " + cls + "." + method, e); }
    }
    static void edit(TodoModel m, long id, String title) {
        invoke("com.supercubegame.pockettodo.TodoModel", "edit", m, new Class<?>[]{long.class, String.class}, id, title);
    }
    static byte[] backup(TodoModel m) {
        return (byte[])invoke("com.supercubegame.pockettodo.BackupCodec", "encode", null, new Class<?>[]{TodoModel.class}, m);
    }
    static TodoModel restore(byte[] b) {
        return (TodoModel)invoke("com.supercubegame.pockettodo.BackupCodec", "decode", null, new Class<?>[]{byte[].class}, (Object)b);
    }
    static byte[] envelope(String state) {
        try {
            StringBuilder hex = new StringBuilder();
            for (byte b : MessageDigest.getInstance("SHA-256").digest(state.getBytes(StandardCharsets.US_ASCII))) hex.append(String.format("%02x", b & 255));
            return ("POCKET_TODO_BACKUP\n1\n" + hex + "\n" + state + "\n").getBytes(StandardCharsets.US_ASCII);
        } catch (Exception e) { throw new AssertionError(e); }
    }
    public static void main(String[] args) {
        TodoModel m = new TodoModel();
        check(m.items().isEmpty(), "fresh install is empty");
        rejects(() -> m.add(" \n\t "), "blank rejected");
        rejects(() -> m.add(null), "null rejected");
        rejects(() -> m.add("x".repeat(201)), "overlong rejected");
        long a = m.add("  Buy milk  ");
        long b = m.add("中文待办 😀");
        check(a != b, "stable distinct ids");
        check(m.items().get(0).title.equals("Buy milk"), "trim title");
        check(!m.items().get(0).done, "new item unfinished");
        m.toggle(a);
        check(m.items().get(0).done, "toggle complete");
        m.toggle(a);
        check(!m.items().get(0).done, "toggle back");
        m.toggle(b);
        String saved = m.encode();
        TodoModel restored = TodoModel.decode(saved);
        check(restored.items().size() == 2, "restore exact count");
        check(restored.items().get(1).title.equals("中文待办 😀"), "restore Unicode");
        check(restored.items().get(1).done, "restore completed state");
        check(restored.encode().equals(saved), "canonical roundtrip");
        restored.remove(a);
        check(restored.items().size() == 1 && restored.items().get(0).id == b, "delete exact id");
        check(TodoModel.decode(restored.encode()).items().size() == 1, "deletion persists");
        check(m.items().size() == 2, "snapshot independent");
        long c = restored.add("Next");
        check(c > b, "id does not collide after restore");
        rejects(() -> restored.toggle(99999), "unknown toggle rejected");
        rejects(() -> restored.remove(99999), "unknown delete rejected");
        check(TodoModel.decode("").items().isEmpty(), "empty storage default");
        rejects(() -> TodoModel.decode("not valid"), "corrupt storage rejected");
        rejects(() -> TodoModel.decode(Base64.getEncoder().encodeToString(new byte[]{1,2,3})), "truncated data rejected");
        rejects(() -> TodoModel.decode(saved + "AAAA"), "trailing data rejected");
        boolean immutable = false;
        try { m.items().clear(); } catch (UnsupportedOperationException expected) { immutable = true; }
        check(immutable, "caller cannot mutate collection");
        TodoModel full = new TodoModel();
        for (int i = 0; i < 500; i++) full.add("Task " + i);
        check(full.items().size() == 500, "capacity boundary");
        rejects(() -> full.add("overflow"), "capacity limit enforced");

        edit(m, b, "  改好的待办 😀  ");
        check(m.items().get(1).title.equals("改好的待办 😀"), "edit trims and preserves Unicode");
        check(m.items().get(1).done && m.items().get(1).id == b && m.items().get(0).id == a, "edit preserves completion id and order");
        check(TodoModel.decode(m.encode()).items().get(1).title.equals("改好的待办 😀"), "edit survives serialization");
        String before = m.encode();
        rejects(() -> edit(m, b, " \t "), "blank edit rejected");
        rejects(() -> edit(m, b, null), "null edit rejected");
        rejects(() -> edit(m, b, "x".repeat(201)), "overlong edit rejected");
        rejects(() -> edit(m, 99999, "Missing"), "unknown edit rejected");
        check(m.encode().equals(before), "failed edits leave state unchanged");
        edit(m, a, "x".repeat(200));
        check(m.items().get(0).title.length() == 200, "edit length boundary accepted");
        edit(full, 1, "At capacity");
        check(full.items().size() == 500, "editing at capacity works");
        byte[] bytes = backup(m);
        check(restore(bytes).encode().equals(m.encode()), "backup exact roundtrip including ids and completion");
        check(java.util.Arrays.equals(bytes, backup(m)), "backup deterministic");
        check(restore(backup(new TodoModel())).items().isEmpty(), "empty list backup is valid");
        check(restore(backup(full)).items().size() == 500, "capacity backup roundtrip");
        TodoModel max = new TodoModel();
        for (int i = 0; i < 500; i++) max.add("汉".repeat(200));
        check(restore(backup(max)).encode().equals(max.encode()), "max count max Unicode title backup fits limit");
        TodoModel next = restore(bytes);
        check(next.add("Next after import") > b, "import preserves next id");
        String text = new String(bytes, StandardCharsets.US_ASCII);
        rejects(() -> restore(null), "null file rejected");
        rejects(() -> restore(new byte[0]), "empty file rejected");
        rejects(() -> restore(new byte[1000257]), "oversized file rejected");
        rejects(() -> restore(text.replace("POCKET_TODO_BACKUP", "OTHER_APP_BACKUP").getBytes(StandardCharsets.US_ASCII)), "foreign backup rejected");
        rejects(() -> restore(text.replace("\n1\n", "\n2\n").getBytes(StandardCharsets.US_ASCII)), "future version rejected");
        rejects(() -> restore(java.util.Arrays.copyOf(bytes, bytes.length - 8)), "truncated backup rejected");
        rejects(() -> restore((text + "extra").getBytes(StandardCharsets.US_ASCII)), "trailing backup garbage rejected");
        String[] lines = text.split("\n", -1);
        lines[2] = "0".repeat(64);
        rejects(() -> restore(String.join("\n", lines).getBytes(StandardCharsets.US_ASCII)), "checksum mismatch rejected");
        rejects(() -> restore(envelope("not valid")), "checksum alone does not bypass model validation");
        rejects(() -> restore(envelope("")), "missing model payload is not an empty list");
        byte[] raw = Base64.getDecoder().decode(m.encode());
        raw[24] = 0; raw[25] = 0;
        rejects(() -> restore(envelope(Base64.getEncoder().encodeToString(raw))), "malformed model with valid checksum rejected");
        check(m.encode().equals(restore(bytes).encode()), "invalid imports do not mutate source model");
        System.out.println("CORE_RESULT " + checks + "/" + checks + " PASS");
    }
}
