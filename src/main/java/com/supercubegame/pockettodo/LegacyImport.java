package com.supercubegame.pockettodo;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Preview only: importing into the future database requires an explicit transaction.
 * Legacy rows are ordinary todos, never inferred activities, check-ins or money.
 */
public final class LegacyImport {
    private LegacyImport() {}
    public static final class Plan {
        private final List<TodoModel.Item> todos;
        private final String sourceId;
        private Plan(TodoModel model, String sourceId) {
            this.todos = Collections.unmodifiableList(new ArrayList<>(model.items()));
            this.sourceId = sourceId;
        }
        public List<TodoModel.Item> todos() { return todos; }
        public String sourceId() { return sourceId; }
    }
    public static Plan preview(byte[] bytes) {
        if (bytes == null) throw new IllegalArgumentException("缺少旧版备份");
        byte[] owned = bytes.clone();
        TodoModel model = BackupCodec.decode(owned);
        return new Plan(model, MediaRepository.digest(owned));
    }
}
