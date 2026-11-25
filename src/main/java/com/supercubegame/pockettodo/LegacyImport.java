package com.supercubegame.pockettodo;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.function.ToLongFunction;

/** Legacy backups append ordinary todos, never activities, check-ins or money. */
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
    private static Plan decodeOwned(byte[] owned) {
        TodoModel model = BackupCodec.decode(owned);
        return new Plan(model, MediaRepository.digest(owned));
    }
    public static Plan preview(byte[] bytes) {
        if (bytes == null) throw new IllegalArgumentException("缺少旧版备份");
        if (bytes.length > BackupCodec.MAX_BYTES) throw new IllegalArgumentException("旧版备份超过大小限制");
        return decodeOwned(bytes.clone());
    }

    /** Frozen, in-memory only. Do not put this object, its bytes, or consent in a Bundle.
     * The final append uses the exact bytes reviewed, never a second read of a mutable URI. */
    public static final class AppendReview implements AutoCloseable {
        private final int total,completed;
        private final String sourceId;
        private byte[] reviewed;
        private AppendReview(byte[] owned,Plan plan) {
            this.reviewed=owned;this.total=plan.todos().size();this.sourceId=plan.sourceId();
            int count=0;for(TodoModel.Item item:plan.todos())if(item.done)count++;
            this.completed=count;
        }
        public int total(){return total;}
        public int completed(){return completed;}
        public String sourceId(){return sourceId;}
        /** Call only after explicit user confirmation; the database owns same-source replay protection.
         * Consume before calling out. An error or a concurrent callback must not replay the write. */
        public long appendOnce(ToLongFunction<byte[]> append) {
            if(append==null)throw new IllegalArgumentException("缺少追加目标");
            final byte[] bytes;
            synchronized(this){
                if(reviewed==null||total==0)throw new IllegalStateException("没有可追加的预览，请重新选择");
                bytes=reviewed;reviewed=null;
            }
            return append.applyAsLong(bytes);
        }
        @Override public synchronized void close(){reviewed=null;}
    }
    /** Takes ownership of the input stream. A read or close failure yields no review.
     * Limit is the unchanged legacy wire limit, not a count or byte limit for v1.2 todos. */
    public static AppendReview readForAppend(InputStream source)throws IOException {
        if(source==null)throw new IOException("无法读取旧版待办文件");
        final byte[] bytes;
        try(InputStream in=source){
            ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] chunk=new byte[8192];
            while(out.size()<BackupCodec.MAX_BYTES){
                int want=Math.min(chunk.length,BackupCodec.MAX_BYTES-out.size());
                int n=in.read(chunk,0,want);
                if(n==-1)break;
                if(n<=0||n>want)throw new IOException("旧版待办文件读取无进展或长度无效");
                out.write(chunk,0,n);
            }
            if(out.size()==BackupCodec.MAX_BYTES&&in.read()!=-1)throw new IOException("旧版备份超过大小限制");
            bytes=out.toByteArray();
        }
        if(bytes.length>=4&&bytes[0]=='P'&&bytes[1]=='K'&&
            ((bytes[2]==3&&bytes[3]==4)||(bytes[2]==5&&bytes[3]==6)))
            throw new IllegalArgumentException("ZIP 不是旧版待办文件；完整备份请使用单独的恢复入口");
        return new AppendReview(bytes,decodeOwned(bytes));
    }
}
