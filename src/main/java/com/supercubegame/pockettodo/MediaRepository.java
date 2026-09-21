package com.supercubegame.pockettodo;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.FileAlreadyExistsException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/** App-private immutable byte store. Caller owns input streams and supplies a resource budget.
 * This layer does NOT prove bytes are a decodable/safe image. Android must validate dimensions,
 * format and decode separately before attaching an imported asset to a note.
 * Publication uses an atomic create-only hard link; unsupported filesystems fail explicitly.
 * fsync of contents is not a tested guarantee against device power loss/directory durability.
 */
public final class MediaRepository {
    private final Path root;
    private final long maxBytes;
    public MediaRepository(Path directory, long maxBytes) throws IOException {
        if (directory == null || maxBytes <= 0) throw new IllegalArgumentException("无效的媒体目录或字节预算");
        Files.createDirectories(directory);
        if (Files.isSymbolicLink(directory) || !Files.isDirectory(directory, LinkOption.NOFOLLOW_LINKS))
            throw new IOException("媒体目录不能是符号链接");
        this.root = directory.toRealPath();
        this.maxBytes = maxBytes;
    }
    static MessageDigest sha() {
        try { return MessageDigest.getInstance("SHA-256"); }
        catch (NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }
    static String hex(byte[] bytes) {
        StringBuilder out = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) out.append(Character.forDigit((b & 255) >>> 4, 16)).append(Character.forDigit(b & 15, 16));
        return out.toString();
    }
    static String digest(byte[] bytes) { return hex(sha().digest(bytes)); }
    static void validId(String id) {
        if (id == null || !id.matches("[0-9a-f]{64}")) throw new IllegalArgumentException("无效的媒体标识");
    }
    public Path path(String id) throws IOException {
        validId(id);
        Path path = root.resolve(id);
        if (!Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS) || Files.isSymbolicLink(path))
            throw new IOException("媒体不存在或不是普通文件");
        return path;
    }
    public void verify(String id) throws IOException {
        Path p = path(id);
        MessageDigest digest = sha(); long size = 0;
        try (InputStream in = Files.newInputStream(p, StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)) {
            byte[] buffer = new byte[16384]; int n;
            while ((n = in.read(buffer)) != -1) {
                if (n == 0) throw new IOException("媒体读取未取得进展");
                if (n > maxBytes - size) throw new IOException("媒体超过字节预算");
                size += n; digest.update(buffer, 0, n);
            }
        }
        if (size == 0 || !id.equals(hex(digest.digest()))) throw new IOException("媒体内容校验失败");
    }
    public synchronized String copy(InputStream source) throws IOException {
        if (source == null) throw new IllegalArgumentException("缺少媒体输入");
        Path temp = Files.createTempFile(root, ".import-", ".part");
        try {
            MessageDigest digest = sha(); long size = 0;
            try (OutputStream out = Files.newOutputStream(temp, StandardOpenOption.WRITE, StandardOpenOption.TRUNCATE_EXISTING)) {
                byte[] buffer = new byte[16384]; int n;
                while ((n = source.read(buffer)) != -1) {
                    if (n == 0) throw new IOException("媒体读取未取得进展");
                    if (n > maxBytes - size) throw new IOException("媒体超过字节预算，请选择较小文件");
                    size += n; digest.update(buffer, 0, n); out.write(buffer, 0, n);
                }
            }
            if (size == 0) throw new IOException("不能导入空媒体文件");
            try (FileChannel channel = FileChannel.open(temp, StandardOpenOption.WRITE)) { channel.force(true); }
            String id = hex(digest.digest());
            Path dest = root.resolve(id);
            try { Files.createLink(dest, temp); }
            catch (FileAlreadyExistsException exists) { verify(id); }
            verify(id);
            return id;
        } finally { Files.deleteIfExists(temp); }
    }
}
