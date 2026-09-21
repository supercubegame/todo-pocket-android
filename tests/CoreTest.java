import com.supercubegame.pockettodo.TodoModel;
import java.util.Base64;

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
        check(TodoModel.decode("" ).items().isEmpty(), "empty storage default");
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
        System.out.println("CORE_RESULT " + checks + "/" + checks + " PASS");
    }
}
