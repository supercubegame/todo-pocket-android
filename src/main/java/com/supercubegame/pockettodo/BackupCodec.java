package com.supercubegame.pockettodo;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;

/** Versioned, bounded, unencrypted backup. SHA-256 detects damage, not authenticity. */
public final class BackupCodec {
    public static final int MAX_BYTES = 1000256;
    private BackupCodec() {}
    private static String hash(String payload) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(payload.getBytes(StandardCharsets.US_ASCII));
            StringBuilder text = new StringBuilder();
            for (byte b : digest) text.append(Character.forDigit((b & 255) >>> 4, 16)).append(Character.forDigit(b & 15, 16));
            return text.toString();
        } catch (NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }
    public static byte[] encode(TodoModel model) {
        if (model == null) throw new IllegalArgumentException("缺少待办数据");
        String payload = model.encode();
        byte[] bytes = ("POCKET_TODO_BACKUP\n1\n" + hash(payload) + "\n" + payload + "\n").getBytes(StandardCharsets.US_ASCII);
        if (bytes.length > MAX_BYTES) throw new IllegalArgumentException("备份文件过大");
        return bytes;
    }
    public static TodoModel decode(byte[] bytes) {
        if (bytes == null || bytes.length == 0 || bytes.length > MAX_BYTES)
            throw new IllegalArgumentException("备份为空或超过大小限制");
        String text = new String(bytes, StandardCharsets.US_ASCII);
        if (!Arrays.equals(bytes, text.getBytes(StandardCharsets.US_ASCII)))
            throw new IllegalArgumentException("备份文件编码错误");
        String[] fields = text.split("\n", -1);
        if (fields.length != 5 || !fields[0].equals("POCKET_TODO_BACKUP") || !fields[1].equals("1") ||
            !fields[4].isEmpty() || fields[3].isEmpty() || !fields[2].matches("[0-9a-f]{64}"))
            throw new IllegalArgumentException("不是受支持的口袋待办备份");
        if (!MessageDigest.isEqual(fields[2].getBytes(StandardCharsets.US_ASCII), hash(fields[3]).getBytes(StandardCharsets.US_ASCII)))
            throw new IllegalArgumentException("备份校验失败，文件可能已损坏");
        TodoModel model = TodoModel.decode(fields[3]);
        if (!model.encode().equals(fields[3])) throw new IllegalArgumentException("备份数据格式不规范");
        return model;
    }
}
