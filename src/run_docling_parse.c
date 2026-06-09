/*
 * run_docling_parse.c - Batch Docling CLI runner for Windows (v2.0 C port of BAT v1.5)
 * Build: build.bat  (MSVC or MinGW-w64)
 */

#define WIN32_LEAN_AND_MEAN
#define _CRT_SECURE_NO_WARNINGS
#define UNICODE
#define _UNICODE

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <wchar.h>
#include <time.h>
#include <locale.h>

#define VERSION L"2.0.2"
#define DEFAULT_PILLOW_MAX_PIXELS L"2000000000"
#define MAX_PATH_W 4096
#define MAX_KEY 1024
#define MAX_EXT 32
#define MAX_ATTEMPTS 3
#define RETRY_DELAY_SEC 5
#define DEFAULT_DOC_TIMEOUT_SEC 7200
#define MAX_CMD 32768

typedef enum {
    FMT_UNKNOWN = 0,
    FMT_PDF,
    FMT_OFFICE,
    FMT_TEXT,
    FMT_IMAGE,
    FMT_AUDIO,
    FMT_VIDEO,
    FMT_JSON,
    FMT_XML
} FormatKind;

typedef struct {
    wchar_t root[MAX_PATH_W];
    wchar_t input[MAX_PATH_W];
    wchar_t output[MAX_PATH_W];
    wchar_t log_dir[MAX_PATH_W];
    wchar_t work[MAX_PATH_W];
    wchar_t tmp[MAX_PATH_W];
    wchar_t log_file[MAX_PATH_W];
    wchar_t docling_exe[MAX_PATH_W];
    wchar_t input_norm[MAX_PATH_W];
    int total;
    int parsed;
    int skipped;
    int errors;
    int max_attempts;
    int retry_delay_sec;
    int doc_timeout_sec;
    int file_index;
    int file_total;
} Config;

typedef struct {
    wchar_t path[MAX_PATH_W];
    wchar_t ext[MAX_EXT];
    wchar_t display[MAX_PATH_W];
} FileEntry;

typedef struct {
    FormatKind kind;
    const wchar_t *from;
    const wchar_t *pipeline;
    const wchar_t *pdf;
    const wchar_t *tables;
    int ocr_first;
} FormatInfo;

static Config g_cfg;
static FILE *g_log = NULL;
static int g_no_pause = 0;
static wchar_t g_exe_dir[MAX_PATH_W];

/* -------------------------------------------------------------------------- */
static void wcsncpy0(wchar_t *dst, const wchar_t *src, size_t n)
{
    if (n == 0) return;
    wcsncpy(dst, src, n - 1);
    dst[n - 1] = L'\0';
}

static void path_join(wchar_t *dst, size_t cap, const wchar_t *a, const wchar_t *b)
{
    wchar_t tmp[MAX_PATH_W];
    wcsncpy0(tmp, a, MAX_PATH_W);
    size_t len = wcslen(tmp);
    if (len > 0 && tmp[len - 1] != L'\\' && tmp[len - 1] != L'/') {
        if (len + 1 < MAX_PATH_W) {
            tmp[len] = L'\\';
            tmp[len + 1] = L'\0';
        }
    }
    if (wcslen(tmp) + wcslen(b) < MAX_PATH_W)
        wcscat(tmp, b);
    wcsncpy0(dst, tmp, cap);
}

static int ensure_dir(const wchar_t *path)
{
    wchar_t buf[MAX_PATH_W];
    wcsncpy0(buf, path, MAX_PATH_W);
    for (wchar_t *p = buf + 3; *p; p++) {
        if (*p == L'\\' || *p == L'/') {
            wchar_t c = *p;
            *p = L'\0';
            if (wcslen(buf) > 0 && GetFileAttributesW(buf) == INVALID_FILE_ATTRIBUTES)
                CreateDirectoryW(buf, NULL);
            *p = c;
        }
    }
    if (GetFileAttributesW(buf) == INVALID_FILE_ATTRIBUTES)
        return CreateDirectoryW(buf, NULL) || GetLastError() == ERROR_ALREADY_EXISTS;
    return 1;
}

static int file_exists(const wchar_t *path)
{
    DWORD a = GetFileAttributesW(path);
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}

static int dir_exists(const wchar_t *path)
{
    DWORD a = GetFileAttributesW(path);
    return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY);
}

static void append_log(const wchar_t *fmt, ...)
{
    if (!g_log) return;
    va_list ap;
    va_start(ap, fmt);
    vfwprintf(g_log, fmt, ap);
    va_end(ap);
    fputwc(L'\n', g_log);
    fflush(g_log);
}

static void print_line(const wchar_t *s)
{
    if (!s || !*s) {
        putchar('\n');
        return;
    }
    wprintf(L"%ls\n", s);
}

static void print_status(const wchar_t *tag, const wchar_t *name)
{
    wprintf(L"%ls %ls\n", tag, name);
}

static void make_log_timestamp(wchar_t *stamp, size_t cap)
{
    SYSTEMTIME st;
    GetLocalTime(&st);
    unsigned r = (unsigned)rand();
    swprintf(stamp, cap, L"%04u%02u%02u_%02u%02u%02u_%u",
             st.wYear, st.wMonth, st.wDay,
             st.wHour, st.wMinute, st.wSecond, r);
}

static int find_docling(wchar_t *out, size_t cap)
{
    DWORD n = SearchPathW(NULL, L"docling", L".exe", (DWORD)cap, out, NULL);
    if (n > 0) return 1;
    n = SearchPathW(NULL, L"docling", L".cmd", (DWORD)cap, out, NULL);
    if (n > 0) return 1;
    n = SearchPathW(NULL, L"docling", NULL, (DWORD)cap, out, NULL);
    return n > 0;
}

static int wcsieq(const wchar_t *a, const wchar_t *b)
{
    return _wcsicmp(a, b) == 0;
}

static int is_supported_ext(const wchar_t *ext)
{
    static const wchar_t *list[] = {
        L"pdf", L"docx", L"xlsx", L"pptx",
        L"md", L"markdown", L"adoc", L"asciidoc", L"tex",
        L"html", L"htm", L"xhtml", L"csv", L"vtt",
        L"png", L"jpg", L"jpeg", L"tif", L"tiff", L"bmp", L"webp",
        L"wav", L"mp3", L"m4a", L"aac", L"ogg", L"flac",
        L"mp4", L"avi", L"mov", L"json", L"xml", NULL
    };
    for (int i = 0; list[i]; i++)
        if (wcsieq(ext, list[i])) return 1;
    return 0;
}

static void resolve_format(const wchar_t *ext, FormatInfo *fi)
{
    memset(fi, 0, sizeof(*fi));
    fi->kind = FMT_UNKNOWN;
    fi->tables = L"--no-tables";
    fi->ocr_first = 0;

    if (wcsieq(ext, L"pdf")) {
        fi->kind = FMT_PDF;
        fi->from = L"--from pdf";
        fi->pdf = L"--pdf-backend pypdfium2";
        fi->tables = L"--tables --table-mode accurate";
        fi->ocr_first = 1;
        return;
    }
    if (wcsieq(ext, L"docx")) {
        fi->kind = FMT_OFFICE;
        fi->from = L"--from docx";
        fi->tables = L"--tables --table-mode accurate";
        return;
    }
    if (wcsieq(ext, L"xlsx")) {
        fi->kind = FMT_OFFICE;
        fi->from = L"--from xlsx";
        fi->tables = L"--tables --table-mode accurate";
        return;
    }
    if (wcsieq(ext, L"pptx")) {
        fi->kind = FMT_OFFICE;
        fi->from = L"--from pptx";
        fi->tables = L"--tables --table-mode accurate";
        return;
    }
    if (wcsieq(ext, L"md") || wcsieq(ext, L"markdown")) {
        fi->kind = FMT_TEXT;
        fi->from = L"--from md";
        return;
    }
    if (wcsieq(ext, L"adoc") || wcsieq(ext, L"asciidoc")) {
        fi->kind = FMT_TEXT;
        fi->from = L"--from asciidoc";
        return;
    }
    if (wcsieq(ext, L"tex")) {
        fi->kind = FMT_TEXT;
        fi->from = L"--from latex";
        return;
    }
    if (wcsieq(ext, L"html") || wcsieq(ext, L"htm") || wcsieq(ext, L"xhtml")) {
        fi->kind = FMT_TEXT;
        fi->from = L"--from html";
        return;
    }
    if (wcsieq(ext, L"csv")) {
        fi->kind = FMT_TEXT;
        fi->from = L"--from csv";
        fi->tables = L"--tables --table-mode accurate";
        return;
    }
    if (wcsieq(ext, L"vtt")) {
        fi->kind = FMT_TEXT;
        fi->from = L"--from vtt";
        return;
    }
    if (wcsieq(ext, L"json")) {
        fi->kind = FMT_JSON;
        fi->from = L"--from json_docling";
        return;
    }
    if (wcsieq(ext, L"xml")) {
        fi->kind = FMT_XML;
        return;
    }
    if (wcsieq(ext, L"png") || wcsieq(ext, L"jpg") || wcsieq(ext, L"jpeg") ||
        wcsieq(ext, L"tif") || wcsieq(ext, L"tiff") || wcsieq(ext, L"bmp") ||
        wcsieq(ext, L"webp")) {
        fi->kind = FMT_IMAGE;
        fi->from = L"--from image";
        fi->ocr_first = 1;
        return;
    }
    if (wcsieq(ext, L"wav") || wcsieq(ext, L"mp3") || wcsieq(ext, L"m4a") ||
        wcsieq(ext, L"aac") || wcsieq(ext, L"ogg") || wcsieq(ext, L"flac")) {
        fi->kind = FMT_AUDIO;
        fi->from = L"--from audio";
        fi->pipeline = L"--pipeline asr --asr-model whisper_tiny";
        return;
    }
    if (wcsieq(ext, L"mp4") || wcsieq(ext, L"avi") || wcsieq(ext, L"mov")) {
        fi->kind = FMT_VIDEO;
        fi->from = L"--from audio";
        fi->pipeline = L"--pipeline asr --asr-model whisper_tiny";
        return;
    }
}

static void get_output_key(const wchar_t *src_file, wchar_t *out_key, size_t cap)
{
    wchar_t src_dir[MAX_PATH_W];
    wchar_t base[MAX_PATH_W];
    wchar_t rel[MAX_PATH_W];

    wcsncpy0(src_dir, src_file, MAX_PATH_W);
    wchar_t *slash = wcsrchr(src_dir, L'\\');
    if (!slash) slash = wcsrchr(src_dir, L'/');
    if (slash) {
        wcsncpy0(base, slash + 1, MAX_PATH_W);
        *slash = L'\0';
    } else {
        wcsncpy0(base, src_file, MAX_PATH_W);
        src_dir[0] = L'\0';
    }
    wchar_t *dot = wcsrchr(base, L'.');
    if (dot) *dot = L'\0';

    size_t norm_len = wcslen(g_cfg.input_norm);
    if (_wcsnicmp(src_dir, g_cfg.input_norm, norm_len) == 0) {
        const wchar_t *rest = src_dir + norm_len;
        if (*rest == L'\\' || *rest == L'/') rest++;
        wcsncpy0(rel, rest, MAX_PATH_W);
    } else {
        rel[0] = L'\0';
    }

    if (rel[0] == L'\0') {
        wcsncpy0(out_key, base, cap);
        return;
    }
    for (wchar_t *p = rel; *p; p++)
        if (*p == L'\\' || *p == L'/') *p = L'_';
    size_t rlen = wcslen(rel);
    if (rlen > 0 && rel[rlen - 1] == L'_') rel[rlen - 1] = L'\0';
    swprintf(out_key, cap, L"%s_%s", rel, base);
}

static int is_output_complete(const wchar_t *key)
{
    wchar_t md[MAX_PATH_W], html[MAX_PATH_W];
    swprintf(md, MAX_PATH_W, L"%s\\%s.md", g_cfg.output, key);
    swprintf(html, MAX_PATH_W, L"%s\\%s.html", g_cfg.output, key);
    return file_exists(md) && file_exists(html);
}

static void delete_if_exists(const wchar_t *path)
{
    if (file_exists(path)) DeleteFileW(path);
}

static void remove_dir_recursive(const wchar_t *dir)
{
    wchar_t pattern[MAX_PATH_W];
    path_join(pattern, MAX_PATH_W, dir, L"*");
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW(pattern, &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        if (wcscmp(fd.cFileName, L".") == 0 || wcscmp(fd.cFileName, L"..") == 0)
            continue;
        wchar_t full[MAX_PATH_W];
        path_join(full, MAX_PATH_W, dir, fd.cFileName);
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)
            remove_dir_recursive(full);
        else
            DeleteFileW(full);
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    RemoveDirectoryW(dir);
}

static void cleanup_output_artifacts(const wchar_t *key)
{
    if (!key || !*key) return;
    wchar_t p[MAX_PATH_W];
    swprintf(p, MAX_PATH_W, L"%s\\%s.md", g_cfg.output, key);
    delete_if_exists(p);
    swprintf(p, MAX_PATH_W, L"%s\\%s.html", g_cfg.output, key);
    delete_if_exists(p);
    swprintf(p, MAX_PATH_W, L"%s\\%s.json", g_cfg.output, key);
    delete_if_exists(p);
    swprintf(p, MAX_PATH_W, L"%s\\%s.txt", g_cfg.output, key);
    delete_if_exists(p);
    swprintf(p, MAX_PATH_W, L"%s\\%s", g_cfg.output, key);
    if (dir_exists(p)) remove_dir_recursive(p);
}

static void remove_unwanted_outputs(const wchar_t *key)
{
    wchar_t p[MAX_PATH_W];
    swprintf(p, MAX_PATH_W, L"%s\\%s.json", g_cfg.output, key);
    delete_if_exists(p);
    swprintf(p, MAX_PATH_W, L"%s\\%s.txt", g_cfg.output, key);
    delete_if_exists(p);
    swprintf(p, MAX_PATH_W, L"%s\\%s", g_cfg.output, key);
    if (dir_exists(p)) remove_dir_recursive(p);
    swprintf(p, MAX_PATH_W, L"%s\\%s_artifacts", g_cfg.output, key);
    if (dir_exists(p)) remove_dir_recursive(p);
}

static void rename_job_outputs(const wchar_t *job_id, const wchar_t *out_key)
{
    if (_wcsicmp(job_id, out_key) == 0) return;
    wchar_t src[MAX_PATH_W], dst[MAX_PATH_W];
    swprintf(src, MAX_PATH_W, L"%s\\%s.md", g_cfg.output, job_id);
    swprintf(dst, MAX_PATH_W, L"%s\\%s.md", g_cfg.output, out_key);
    if (file_exists(src)) MoveFileExW(src, dst, MOVEFILE_REPLACE_EXISTING);
    swprintf(src, MAX_PATH_W, L"%s\\%s.html", g_cfg.output, job_id);
    swprintf(dst, MAX_PATH_W, L"%s\\%s.html", g_cfg.output, out_key);
    if (file_exists(src)) MoveFileExW(src, dst, MOVEFILE_REPLACE_EXISTING);
}

static const wchar_t *format_kind_name(FormatKind k)
{
    switch (k) {
    case FMT_PDF: return L"pdf";
    case FMT_OFFICE: return L"office";
    case FMT_TEXT: return L"text";
    case FMT_IMAGE: return L"image";
    case FMT_AUDIO: return L"audio";
    case FMT_VIDEO: return L"video";
    case FMT_JSON: return L"json";
    case FMT_XML: return L"xml";
    default: return L"unknown";
    }
}

static int make_work_copy(const wchar_t *src, const wchar_t *dot_ext,
                          const wchar_t *out_key, wchar_t *work_src, size_t ws_cap,
                          wchar_t *job_id, size_t jid_cap)
{
    unsigned r = (unsigned)(GetTickCount64() & 0x7fffffff) ^ (unsigned)rand();
    swprintf(job_id, jid_cap, L"job_%d_%u", g_cfg.total, r);
    wchar_t dest[MAX_PATH_W];
    swprintf(dest, MAX_PATH_W, L"%s\\%s%s", g_cfg.work, job_id, dot_ext);

    if (CopyFileW(src, dest, FALSE)) {
        wcsncpy0(work_src, dest, ws_cap);
        append_log(L"Work copy: %s", dest);
        return 1;
    }
    append_log(L"Copy fail, direct path: %s", src);
    wcsncpy0(work_src, src, ws_cap);
    wcsncpy0(job_id, out_key, jid_cap);
    return 1;
}

static int build_docling_cmd(wchar_t *cmd, size_t cap, const wchar_t *src,
                             const FormatInfo *fi, int attempt, int use_ocr)
{
    wchar_t ocr[32];
    if (use_ocr) wcscpy(ocr, L"--ocr");
    else wcscpy(ocr, L"--no-ocr");

    wchar_t timeout[64] = L"";
    if (g_cfg.doc_timeout_sec > 0)
        swprintf(timeout, 64, L"--document-timeout %d", g_cfg.doc_timeout_sec);

    int n = swprintf(cmd, cap,
        L"\"%s\" --to md --to html --output \"%s\" %s %s %s %s %s %s "
        L"--image-export-mode placeholder -v \"%s\"",
        g_cfg.docling_exe, g_cfg.output,
        fi->from ? fi->from : L"",
        fi->pipeline ? fi->pipeline : L"",
        fi->pdf ? fi->pdf : L"",
        ocr,
        fi->tables ? fi->tables : L"--no-tables",
        timeout,
        src);

    (void)attempt;
    return n > 0 && (size_t)n < cap;
}

/* Run docling; stream stdout/stderr to log in real time. Returns process exit code. */
static int run_docling_process(const wchar_t *cmdline)
{
    wchar_t wrapped[MAX_CMD + 512];
    const wchar_t *pillow = _wgetenv(L"PILLOW_MAX_IMAGE_PIXELS");
    if (!pillow || !pillow[0]) pillow = DEFAULT_PILLOW_MAX_PIXELS;

    int wn = swprintf(wrapped, MAX_CMD + 512,
        L"cmd.exe /c set PILLOW_MAX_IMAGE_PIXELS=%s& set PYTHONUTF8=1& "
        L"set PYTHONIOENCODING=utf-8& %s",
        pillow, cmdline);
    if (wn <= 0 || wn >= MAX_CMD + 512) {
        append_log(L"ERROR: wrapped command too long");
        return -1;
    }

    SECURITY_ATTRIBUTES sa;
    sa.nLength = sizeof(sa);
    sa.bInheritHandle = TRUE;
    sa.lpSecurityDescriptor = NULL;

    HANDLE read_pipe = NULL, write_pipe = NULL;
    if (!CreatePipe(&read_pipe, &write_pipe, &sa, 0))
        return -1;
    SetHandleInformation(read_pipe, HANDLE_FLAG_INHERIT, 0);

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    ZeroMemory(&pi, sizeof(pi));
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW;
    si.hStdOutput = write_pipe;
    si.hStdError = write_pipe;
    si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    si.wShowWindow = SW_HIDE;

    wchar_t *mutable_cmd = _wcsdup(wrapped);
    if (!mutable_cmd) {
        CloseHandle(read_pipe);
        CloseHandle(write_pipe);
        return -1;
    }

    BOOL ok = CreateProcessW(
        NULL, mutable_cmd, NULL, NULL, TRUE,
        CREATE_NO_WINDOW,
        NULL, NULL, &si, &pi);

    CloseHandle(write_pipe);
    free(mutable_cmd);

    if (!ok) {
        append_log(L"CreateProcess failed: %lu", GetLastError());
        CloseHandle(read_pipe);
        return -1;
    }

    char buf[4096];
    DWORD read_bytes;
    while (ReadFile(read_pipe, buf, sizeof(buf) - 1, &read_bytes, NULL) && read_bytes > 0) {
        buf[read_bytes] = '\0';
        fputs(buf, g_log);
        fflush(g_log);
    }
    CloseHandle(read_pipe);

    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD exit_code = 1;
    GetExitCodeProcess(pi.hProcess, &exit_code);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    return (int)exit_code;
}

static int run_docling_with_retry(const wchar_t *cli_src, const wchar_t *job_id,
                                  const wchar_t *out_key, const wchar_t *ext)
{
    FormatInfo fi;
    resolve_format(ext, &fi);
    if (fi.kind == FMT_UNKNOWN) return 0;

    wchar_t cmd[MAX_CMD];
    for (int attempt = 1; attempt <= g_cfg.max_attempts; attempt++) {
        cleanup_output_artifacts(job_id);
        cleanup_output_artifacts(out_key);

        int use_ocr = fi.ocr_first;
        if (attempt >= 2 && (fi.kind == FMT_PDF || fi.kind == FMT_IMAGE))
            use_ocr = 0;

        append_log(L"Attempt %d/%d %s job=%s out=%s ocr=%s",
                   attempt, g_cfg.max_attempts, format_kind_name(fi.kind),
                   job_id, out_key, use_ocr ? L"yes" : L"no");

        wprintf(L"  -> attempt %d/%d (%s%s)\n", attempt, g_cfg.max_attempts,
                format_kind_name(fi.kind), use_ocr ? L", OCR" : L"");

        if (!build_docling_cmd(cmd, MAX_CMD, cli_src, &fi, attempt, use_ocr)) {
            append_log(L"ERROR: command line too long");
            return 0;
        }

        int code = run_docling_process(cmd);
        if (code == 0) {
            if (is_output_complete(job_id)) {
                rename_job_outputs(job_id, out_key);
                if (is_output_complete(out_key)) {
                    remove_unwanted_outputs(job_id);
                    remove_unwanted_outputs(out_key);
                    return 1;
                }
            }
            append_log(L"WARN: docling ok but missing output for %s", out_key);
        } else {
            append_log(L"WARN: docling exit code %d", code);
        }

        if (attempt < g_cfg.max_attempts) {
            append_log(L"Retry in %d s...", g_cfg.retry_delay_sec);
            Sleep((DWORD)g_cfg.retry_delay_sec * 1000);
        }
    }

    cleanup_output_artifacts(job_id);
    cleanup_output_artifacts(out_key);
    return 0;
}

static int is_office_temp(const wchar_t *name)
{
    return name[0] == L'~' && name[1] == L'$';
}

static void get_basename(const wchar_t *path, wchar_t *out, size_t cap)
{
    const wchar_t *p = wcsrchr(path, L'\\');
    if (!p) p = wcsrchr(path, L'/');
    wcsncpy0(out, p ? p + 1 : path, cap);
}

static void get_extension(const wchar_t *path, wchar_t *ext, size_t cap)
{
    const wchar_t *dot = wcsrchr(path, L'.');
    if (!dot || dot == path) {
        ext[0] = L'\0';
        return;
    }
    wcsncpy0(ext, dot + 1, cap);
}

static int scan_directory(const wchar_t *dir, FileEntry **entries, int *count, int *capacity)
{
    wchar_t pattern[MAX_PATH_W];
    path_join(pattern, MAX_PATH_W, dir, L"*");

    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW(pattern, &fd);
    if (h == INVALID_HANDLE_VALUE) return 0;

    do {
        if (wcscmp(fd.cFileName, L".") == 0 || wcscmp(fd.cFileName, L"..") == 0)
            continue;

        wchar_t full[MAX_PATH_W];
        path_join(full, MAX_PATH_W, dir, fd.cFileName);

        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            scan_directory(full, entries, count, capacity);
            continue;
        }

        if (is_office_temp(fd.cFileName)) continue;

        wchar_t ext[MAX_EXT];
        get_extension(full, ext, MAX_EXT);
        if (!ext[0] || !is_supported_ext(ext)) continue;

        if (*count >= *capacity) {
            int new_cap = *capacity ? *capacity * 2 : 64;
            FileEntry *n = (FileEntry *)realloc(*entries, (size_t)new_cap * sizeof(FileEntry));
            if (!n) break;
            *entries = n;
            *capacity = new_cap;
        }

        FileEntry *e = &(*entries)[*count];
        wcsncpy0(e->path, full, MAX_PATH_W);
        wcsncpy0(e->ext, ext, MAX_EXT);
        get_basename(full, e->display, MAX_PATH_W);
        (*count)++;
    } while (FindNextFileW(h, &fd));

    FindClose(h);
    return 1;
}

static void handle_one_file(const FileEntry *fe)
{
    g_cfg.total++;
    g_cfg.file_index++;

    wchar_t out_key[MAX_KEY];
    get_output_key(fe->path, out_key, MAX_KEY);
    if (!out_key[0]) return;

    if (is_output_complete(out_key)) {
        g_cfg.skipped++;
        print_status(L"[SKIP]", fe->display);
        append_log(L"[SKIP] %s", fe->path);
        return;
    }

    int pct = g_cfg.file_total > 0 ? (g_cfg.file_index * 100) / g_cfg.file_total : 0;
    wprintf(L"[%3d%%] %d/%d ", pct, g_cfg.file_index, g_cfg.file_total);
    print_status(L"[PARSE]", fe->display);
    append_log(L"[PARSE] %s key=%s", fe->path, out_key);

    wchar_t dot_ext[16];
    swprintf(dot_ext, 16, L".%s", fe->ext);

    wchar_t work_src[MAX_PATH_W];
    wchar_t job_id[MAX_KEY];
    if (!make_work_copy(fe->path, dot_ext, out_key, work_src, MAX_PATH_W, job_id, MAX_KEY)) {
        g_cfg.errors++;
        print_status(L"[ERROR]", fe->display);
        append_log(L"[ERROR] no work file");
        return;
    }

    int ok = run_docling_with_retry(work_src, job_id, out_key, fe->ext);

    if (work_src[0] && _wcsicmp(work_src, fe->path) != 0)
        DeleteFileW(work_src);

    if (!ok) {
        g_cfg.errors++;
        print_status(L"[ERROR]", fe->display);
        append_log(L"[ERROR] %s", fe->path);
        cleanup_output_artifacts(job_id);
        cleanup_output_artifacts(out_key);
        return;
    }

    g_cfg.parsed++;
    print_status(L"[OK]", fe->display);
    append_log(L"[OK] %s", fe->path);
    remove_unwanted_outputs(job_id);
    remove_unwanted_outputs(out_key);
}

static void get_exe_directory(wchar_t *dir, size_t cap)
{
    wchar_t path[MAX_PATH_W];
    DWORD n = GetModuleFileNameW(NULL, path, MAX_PATH_W);
    if (n == 0 || n >= MAX_PATH_W) {
        dir[0] = L'\0';
        return;
    }
    wchar_t *slash = wcsrchr(path, L'\\');
    if (!slash) slash = wcsrchr(path, L'/');
    if (slash) *slash = L'\0';
    wcsncpy0(dir, path, cap);
}

static void setup_console(void)
{
    if (!GetConsoleWindow()) {
        if (!AttachConsole(ATTACH_PARENT_PROCESS))
            AllocConsole();
#if defined(_MSC_VER)
        FILE *fp;
        freopen_s(&fp, "CONOUT$", "w", stdout);
        freopen_s(&fp, "CONOUT$", "w", stderr);
        freopen_s(&fp, "CONIN$", "r", stdin);
#else
        freopen("CONOUT$", "w", stdout);
        freopen("CONOUT$", "w", stderr);
        freopen("CONIN$", "r", stdin);
#endif
    }

    SetConsoleTitleW(L"Docling batch parse v2.0");
    SetConsoleOutputCP(CP_UTF8);
    SetConsoleCP(CP_UTF8);
}

static void setup_environment(void)
{
    const wchar_t *pillow_max = _wgetenv(L"PILLOW_MAX_IMAGE_PIXELS");
    if (!pillow_max || !pillow_max[0])
        pillow_max = _wgetenv(L"DOCLING_PILLOW_MAX_PIXELS");
    if (!pillow_max || !pillow_max[0])
        pillow_max = DEFAULT_PILLOW_MAX_PIXELS;

    SetEnvironmentVariableW(L"PYTHONUTF8", L"1");
    SetEnvironmentVariableW(L"PYTHONIOENCODING", L"utf-8");
    SetEnvironmentVariableW(L"PILLOW_MAX_IMAGE_PIXELS", pillow_max);
    SetEnvironmentVariableW(L"TEMP", g_cfg.tmp);
    SetEnvironmentVariableW(L"TMP", g_cfg.tmp);
    _wsetlocale(LC_ALL, L"");
}

static void wait_before_exit(void)
{
    if (g_no_pause) return;
    if (_wgetenv(L"DOCLING_NO_PAUSE")) return;

    HANDLE hin = GetStdHandle(STD_INPUT_HANDLE);
    DWORD mode = 0;
    if (hin == INVALID_HANDLE_VALUE || !GetConsoleMode(hin, &mode))
        return;

    print_line(L"");
    print_line(L"Gotovo. Nazhmite Enter dlya zakrytiya...");
    fflush(stdout);
    int ch;
    while ((ch = getwchar()) != L'\n' && ch != WEOF) { }
}

static int parse_args(int argc, wchar_t **argv)
{
    for (int i = 1; i < argc; i++) {
        if (wcsieq(argv[i], L"--no-pause") || wcsieq(argv[i], L"-n"))
            g_no_pause = 1;
        else if (wcsieq(argv[i], L"--help") || wcsieq(argv[i], L"-h") || wcsieq(argv[i], L"/?")) {
            wprintf(L"run_docling_parse.exe  — paketnyj parsing Docling (md+html)\n\n");
            wprintf(L"  --no-pause, -n     ne zhdat Enter v konce (dlya avtomatizacii)\n");
            wprintf(L"  DOCLING_ROOT       kornevaya papka (docs, parsed, logs, work)\n");
            wprintf(L"  DOCLING_TIMEOUT    tajmaut dokumenta v sekundah (0 = bez limita)\n");
            wprintf(L"  DOCLING_NO_PAUSE=1 to zhe chto --no-pause\n");
            wprintf(L"  PILLOW_MAX_IMAGE_PIXELS  limit Pillow dlya bolshih PNG (def. 1e9)\n\n");
            wprintf(L"Po umolchaniju ROOT = papka s exe, inache DOCLING_ROOT.\n");
            return 0;
        }
    }
    return 1;
}

static int load_config(void)
{
    memset(&g_cfg, 0, sizeof(g_cfg));
    g_cfg.max_attempts = MAX_ATTEMPTS;
    g_cfg.retry_delay_sec = RETRY_DELAY_SEC;
    g_cfg.doc_timeout_sec = DEFAULT_DOC_TIMEOUT_SEC;

    get_exe_directory(g_exe_dir, MAX_PATH_W);

    const wchar_t *root_env = _wgetenv(L"DOCLING_ROOT");
    if (root_env && root_env[0])
        wcsncpy0(g_cfg.root, root_env, MAX_PATH_W);
    else if (g_exe_dir[0])
        wcsncpy0(g_cfg.root, g_exe_dir, MAX_PATH_W);
    else
        wcsncpy0(g_cfg.root, L"C:\\Users\\andrey.danilov\\Documents\\VTB\\docling", MAX_PATH_W);

    const wchar_t *to_env = _wgetenv(L"DOCLING_TIMEOUT");
    if (to_env && to_env[0])
        g_cfg.doc_timeout_sec = _wtoi(to_env);

    path_join(g_cfg.input, MAX_PATH_W, g_cfg.root, L"docs");
    path_join(g_cfg.output, MAX_PATH_W, g_cfg.root, L"parsed");
    path_join(g_cfg.log_dir, MAX_PATH_W, g_cfg.root, L"logs");
    path_join(g_cfg.work, MAX_PATH_W, g_cfg.root, L"work");
    path_join(g_cfg.tmp, MAX_PATH_W, g_cfg.work, L"tmp");

    wcsncpy0(g_cfg.input_norm, g_cfg.input, MAX_PATH_W);
    size_t len = wcslen(g_cfg.input_norm);
    while (len > 0 && (g_cfg.input_norm[len - 1] == L'\\' || g_cfg.input_norm[len - 1] == L'/'))
        g_cfg.input_norm[--len] = L'\0';

    return 1;
}

int wmain(int argc, wchar_t **argv)
{
    setup_console();

    if (!parse_args(argc, argv))
        return 0;

    srand((unsigned)time(NULL) ^ (unsigned)GetTickCount64());
    load_config();
    setup_environment();

    print_line(L"========================================");
    wprintf(L"Docling batch parse - v%ls (C)\n", VERSION);
    print_line(L"========================================");
    wprintf(L"Exe:   %s\n", g_exe_dir);
    wprintf(L"Root:  %s\n", g_cfg.root);
    print_line(L"Vyhod: md + html");
    print_line(L"========================================");

    if (!find_docling(g_cfg.docling_exe, MAX_PATH_W)) {
        print_line(L"OSHIBKA: docling ne v PATH. pip install docling");
        wait_before_exit();
        return 1;
    }

    if (!dir_exists(g_cfg.input)) {
        print_line(L"OSHIBKA: net papki docs");
        wprintf(L"%s\n", g_cfg.input);
        wait_before_exit();
        return 1;
    }

    ensure_dir(g_cfg.output);
    ensure_dir(g_cfg.log_dir);
    ensure_dir(g_cfg.work);
    ensure_dir(g_cfg.tmp);

    wchar_t stamp[64];
    make_log_timestamp(stamp, 64);
    swprintf(g_cfg.log_file, MAX_PATH_W, L"%s\\docling_%s.log", g_cfg.log_dir, stamp);
    g_log = _wfopen(g_cfg.log_file, L"w, ccs=UTF-8");
    if (!g_log)
        g_log = _wfopen(g_cfg.log_file, L"w");

    append_log(L"Started v%ls", VERSION);
    append_log(L"Docling: %s", g_cfg.docling_exe);
    append_log(L"PILLOW_MAX_IMAGE_PIXELS=%s",
               _wgetenv(L"PILLOW_MAX_IMAGE_PIXELS") ? _wgetenv(L"PILLOW_MAX_IMAGE_PIXELS")
                                                   : DEFAULT_PILLOW_MAX_PIXELS);
    if (g_cfg.doc_timeout_sec > 0)
        append_log(L"Document timeout: %d sec", g_cfg.doc_timeout_sec);

    wprintf(L"\nInput:   %s\n", g_cfg.input);
    wprintf(L"Output:  %s\n", g_cfg.output);
    wprintf(L"Log:     %s\n\n", g_cfg.log_file);

    FileEntry *entries = NULL;
    int count = 0, capacity = 0;
    print_line(L"Skanirovanie...");
    scan_directory(g_cfg.input, &entries, &count, &capacity);
    g_cfg.file_total = count;

    if (count == 0)
        print_line(L"VNIMANIE: podderzhivaemye fajly ne najdeny v docs");
    else
        wprintf(L"Najdeno fajlov: %d\n\n", count);

    for (int i = 0; i < count; i++)
        handle_one_file(&entries[i]);

    free(entries);

    print_line(L"");
    print_line(L"========================================");
    print_line(L"ITOGOVYY OTCHET");
    print_line(L"========================================");
    wprintf(L"Total files found: %d\n", g_cfg.total);
    wprintf(L"Parsed:            %d\n", g_cfg.parsed);
    wprintf(L"Skipped:           %d\n", g_cfg.skipped);
    wprintf(L"Errors:            %d\n", g_cfg.errors);
    print_line(L"========================================");
    wprintf(L"\nLog file:\n%s\n", g_cfg.log_file);

    append_log(L"Done T=%d P=%d S=%d E=%d", g_cfg.total, g_cfg.parsed, g_cfg.skipped, g_cfg.errors);

    if (g_log) fclose(g_log);

    wait_before_exit();
    return g_cfg.errors > 0 ? 1 : 0;
}
