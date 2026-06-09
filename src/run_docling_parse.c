/*
 * run_docling_parse.c - Minimal Windows batch runner for Docling CLI (v3.0)
 *
 * Does one thing: docs\  -->  parsed\  (.md + .html)
 * Build: build.bat
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

#define VERSION           L"3.0.0"
#define MAX_PATH_W        4096
#define MAX_CMD           32768
#define MAX_KEY           1024
#define DEFAULT_PILLOW    L"9999999999"
#define DEFAULT_TIMEOUT   7200

typedef struct {
    wchar_t root[MAX_PATH_W];
    wchar_t docs[MAX_PATH_W];
    wchar_t parsed[MAX_PATH_W];
    wchar_t logs[MAX_PATH_W];
    wchar_t python[MAX_PATH_W];
    wchar_t log_path[MAX_PATH_W];
    wchar_t pillow_pixels[32];
    int doc_timeout_sec;
    int total;
    int done;
    int skipped;
    int failed;
} App;

static App g;
static FILE *g_log = NULL;

/* ------------------------------------------------------------------ utils */

static void wcopy(wchar_t *dst, const wchar_t *src, size_t n)
{
    if (!n) return;
    wcsncpy(dst, src, n - 1);
    dst[n - 1] = L'\0';
}

static void path_join(wchar_t *out, size_t n, const wchar_t *a, const wchar_t *b)
{
    wchar_t t[MAX_PATH_W];
    wcopy(t, a, MAX_PATH_W);
    size_t len = wcslen(t);
    if (len && t[len - 1] != L'\\' && t[len - 1] != L'/') {
        wcscat(t, L"\\");
    }
    wcscat(t, b);
    wcopy(out, t, n);
}

static int path_is_dir(const wchar_t *p)
{
    DWORD a = GetFileAttributesW(p);
    return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY);
}

static int path_is_file(const wchar_t *p)
{
    DWORD a = GetFileAttributesW(p);
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}

static int ensure_dir(const wchar_t *p)
{
    wchar_t buf[MAX_PATH_W];
    wcopy(buf, p, MAX_PATH_W);
    for (wchar_t *c = buf + 2; *c; c++) {
        if (*c == L'\\' || *c == L'/') {
            wchar_t ch = *c;
            *c = L'\0';
            if (!path_is_dir(buf))
                CreateDirectoryW(buf, NULL);
            *c = ch;
        }
    }
    if (!path_is_dir(buf))
        CreateDirectoryW(buf, NULL);
    return path_is_dir(buf);
}

static int ieq(const wchar_t *a, const wchar_t *b)
{
    return _wcsicmp(a, b) == 0;
}

static void logf(const wchar_t *fmt, ...)
{
    if (!g_log) return;
    va_list ap;
    va_start(ap, fmt);
    vfwprintf(g_log, fmt, ap);
    va_end(ap);
    fputwc(L'\n', g_log);
    fflush(g_log);
}

static void say(const wchar_t *s)
{
    wprintf(L"%ls\n", s);
}

static void get_exe_dir(wchar_t *out, size_t n)
{
    wchar_t path[MAX_PATH_W];
    DWORD k = GetModuleFileNameW(NULL, path, MAX_PATH_W);
    if (!k || k >= MAX_PATH_W) {
        out[0] = L'\0';
        return;
    }
    wchar_t *slash = wcsrchr(path, L'\\');
    if (!slash) slash = wcsrchr(path, L'/');
    if (slash) *slash = L'\0';
    wcopy(out, path, n);
}

static void trim_trailing_slash(wchar_t *s)
{
    size_t n = wcslen(s);
    while (n && (s[n - 1] == L'\\' || s[n - 1] == L'/'))
        s[--n] = L'\0';
}

/* ------------------------------------------------------------------ python */

static int find_python(void)
{
    const wchar_t *env = _wgetenv(L"DOCLING_PYTHON");
    if (env && env[0] && path_is_file(env)) {
        wcopy(g.python, env, MAX_PATH_W);
        return 1;
    }

    wchar_t found[MAX_PATH_W];
    if (SearchPathW(NULL, L"python.exe", NULL, MAX_PATH_W, found, NULL)) {
        wcopy(g.python, found, MAX_PATH_W);
        return 1;
    }

    wchar_t docling[MAX_PATH_W];
    if (!SearchPathW(NULL, L"docling.exe", NULL, MAX_PATH_W, docling, NULL))
        return 0;

    wchar_t *slash = wcsrchr(docling, L'\\');
    if (!slash) slash = wcsrchr(docling, L'/');
    if (!slash) return 0;

    wchar_t dir[MAX_PATH_W];
    wcopy(dir, docling, MAX_PATH_W);
    slash = wcsrchr(dir, L'\\');
    if (!slash) slash = wcsrchr(dir, L'/');
    if (!slash) return 0;
    *slash = L'\0';

    path_join(found, MAX_PATH_W, dir, L"python.exe");
    if (!path_is_file(found))
        return 0;

    wcopy(g.python, found, MAX_PATH_W);
    return 1;
}

/* ------------------------------------------------------------------ formats */

static int ext_supported(const wchar_t *ext)
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
        if (ieq(ext, list[i])) return 1;
    return 0;
}

static void get_ext(const wchar_t *path, wchar_t *ext, size_t n)
{
    const wchar_t *dot = wcsrchr(path, L'.');
    if (!dot || dot == path) {
        ext[0] = L'\0';
        return;
    }
    wcopy(ext, dot + 1, n);
}

/* Docling CLI flags per extension (minimal, no BAT parity). */
static const wchar_t *format_flags(const wchar_t *ext)
{
    if (ieq(ext, L"pdf"))
        return L"--from pdf --pdf-backend pypdfium2";
    if (ieq(ext, L"docx")) return L"--from docx --tables";
    if (ieq(ext, L"xlsx")) return L"--from xlsx --tables";
    if (ieq(ext, L"pptx")) return L"--from pptx --tables";
    if (ieq(ext, L"md") || ieq(ext, L"markdown")) return L"--from md";
    if (ieq(ext, L"adoc") || ieq(ext, L"asciidoc")) return L"--from asciidoc";
    if (ieq(ext, L"tex")) return L"--from latex";
    if (ieq(ext, L"html") || ieq(ext, L"htm") || ieq(ext, L"xhtml")) return L"--from html";
    if (ieq(ext, L"csv")) return L"--from csv --tables";
    if (ieq(ext, L"vtt")) return L"--from vtt";
    if (ieq(ext, L"json")) return L"--from json_docling";
    if (ieq(ext, L"png") || ieq(ext, L"jpg") || ieq(ext, L"jpeg") ||
        ieq(ext, L"tif") || ieq(ext, L"tiff") || ieq(ext, L"bmp") || ieq(ext, L"webp"))
        return L"--from image";
    if (ieq(ext, L"wav") || ieq(ext, L"mp3") || ieq(ext, L"m4a") ||
        ieq(ext, L"aac") || ieq(ext, L"ogg") || ieq(ext, L"flac"))
        return L"--from audio --pipeline asr --asr-model whisper_tiny";
    if (ieq(ext, L"mp4") || ieq(ext, L"avi") || ieq(ext, L"mov"))
        return L"--from audio --pipeline asr --asr-model whisper_tiny";
    return L"";
}

/* docs\sub\file.pdf -> sub_file */
static void output_key(const wchar_t *src, wchar_t *key, size_t n)
{
    wchar_t docs_norm[MAX_PATH_W];
    wcopy(docs_norm, g.docs, MAX_PATH_W);
    trim_trailing_slash(docs_norm);

    const wchar_t *rel = src;
    size_t dlen = wcslen(docs_norm);
    if (_wcsnicmp(src, docs_norm, dlen) == 0) {
        rel = src + dlen;
        if (*rel == L'\\' || *rel == L'/') rel++;
    }

    wchar_t stem[MAX_PATH_W];
    wcopy(stem, rel, MAX_PATH_W);
    wchar_t *dot = wcsrchr(stem, L'.');
    if (dot) *dot = L'\0';
    for (wchar_t *p = stem; *p; p++)
        if (*p == L'\\' || *p == L'/') *p = L'_';

    wcopy(key, stem, n);
}

static int output_ready(const wchar_t *key)
{
    wchar_t md[MAX_PATH_W], html[MAX_PATH_W];
    swprintf(md, MAX_PATH_W, L"%s\\%s.md", g.parsed, key);
    swprintf(html, MAX_PATH_W, L"%s\\%s.html", g.parsed, key);
    return path_is_file(md) && path_is_file(html);
}

/* ------------------------------------------------------------------ docling */

static void apply_child_env(void)
{
    SetEnvironmentVariableW(L"PILLOW_MAX_IMAGE_PIXELS", g.pillow_pixels);
    SetEnvironmentVariableW(L"PYTHONUNBUFFERED", L"1");
    SetEnvironmentVariableW(L"PYTHONUTF8", L"1");
    SetEnvironmentVariableW(L"PYTHONIOENCODING", L"utf-8");
}

static void append_file_to_log(const wchar_t *path)
{
    FILE *f = _wfopen(path, L"rb");
    if (!f) return;
    char buf[4096];
    size_t n;
    while ((n = fread(buf, 1, sizeof(buf), f)) > 0)
        fwrite(buf, 1, n, g_log);
    fflush(g_log);
    fclose(f);
}

static int run_docling(const wchar_t *src, const wchar_t *fmt)
{
    wchar_t cmd[MAX_CMD];
    wchar_t timeout[48] = L"";
    if (g.doc_timeout_sec > 0)
        swprintf(timeout, 48, L"--document-timeout %d", g.doc_timeout_sec);

    int n = swprintf(cmd, MAX_CMD,
        L"\"%s\" -m docling --to md --to html --output \"%s\" %s %s "
        L"--image-export-mode placeholder -v \"%s\"",
        g.python, g.parsed, fmt, timeout, src);

    if (n <= 0 || n >= MAX_CMD) {
        logf(L"ERROR command too long: %s", src);
        return -1;
    }

    logf(L"CMD %s", cmd);

    wchar_t cap[MAX_PATH_W];
    swprintf(cap, MAX_PATH_W, L"%s\\_child_%u.log", g.logs,
             (unsigned)(GetTickCount64() & 0xffffffffu));
    DeleteFileW(cap);

    SECURITY_ATTRIBUTES sa = { sizeof(sa), NULL, TRUE };
    HANDLE out = CreateFileW(cap, GENERIC_WRITE, FILE_SHARE_READ, &sa,
                             CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (out == INVALID_HANDLE_VALUE) {
        logf(L"ERROR cannot open capture log");
        return -1;
    }

    apply_child_env();

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    ZeroMemory(&pi, sizeof(pi));
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW;
    si.hStdOutput = out;
    si.hStdError = out;
    si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    si.wShowWindow = SW_HIDE;

    wchar_t *mutable = _wcsdup(cmd);
    if (!mutable) {
        CloseHandle(out);
        return -1;
    }

    BOOL ok = CreateProcessW(NULL, mutable, NULL, NULL, TRUE,
                             CREATE_NO_WINDOW, NULL, g.root, &si, &pi);
    free(mutable);
    CloseHandle(out);

    if (!ok) {
        logf(L"ERROR CreateProcess %lu", GetLastError());
        DeleteFileW(cap);
        return -1;
    }

    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD code = 1;
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);

    append_file_to_log(cap);
    DeleteFileW(cap);
    logf(L"EXIT %lu", code);
    return (int)code;
}

/* ------------------------------------------------------------------ scan */

static void process_file(const wchar_t *path)
{
    if (path[0] == L'~' && path[1] == L'$') return;

    wchar_t ext[32];
    get_ext(path, ext, 32);
    if (!ext[0] || !ext_supported(ext)) return;

    g.total++;

    wchar_t key[MAX_KEY];
    output_key(path, key, MAX_KEY);
    if (!key[0]) return;

    if (output_ready(key)) {
        g.skipped++;
        wprintf(L"[skip] %s\n", key);
        logf(L"[skip] %s", path);
        return;
    }

    const wchar_t *fmt = format_flags(ext);
    if (!fmt[0]) return;

    wprintf(L"[run]  %s\n", key);
    logf(L"[run] %s key=%s", path, key);

    int rc = run_docling(path, fmt);
    if (rc == 0 && output_ready(key)) {
        g.done++;
        wprintf(L"[ok]   %s\n", key);
        logf(L"[ok] %s", path);
        return;
    }

    g.failed++;
    wprintf(L"[fail] %s (code %d)\n", key, rc);
    logf(L"[fail] %s code=%d", path, rc);
}

static void scan_dir(const wchar_t *dir)
{
    wchar_t pattern[MAX_PATH_W];
    swprintf(pattern, MAX_PATH_W, L"%s\\*", dir);

    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW(pattern, &fd);
    if (h == INVALID_HANDLE_VALUE) return;

    do {
        if (ieq(fd.cFileName, L".") || ieq(fd.cFileName, L".."))
            continue;

        wchar_t full[MAX_PATH_W];
        path_join(full, MAX_PATH_W, dir, fd.cFileName);

        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)
            scan_dir(full);
        else
            process_file(full);
    } while (FindNextFileW(h, &fd));

    FindClose(h);
}

/* ------------------------------------------------------------------ main */

static int parse_args(int argc, wchar_t **argv)
{
    for (int i = 1; i < argc; i++) {
        if (ieq(argv[i], L"--help") || ieq(argv[i], L"-h") || ieq(argv[i], L"/?")) {
            wprintf(L"run_docling_parse.exe v%ls\n\n", VERSION);
            wprintf(L"  docs\\ -> parsed\\  (md + html)\n\n");
            wprintf(L"  DOCLING_ROOT          project folder (default: exe dir)\n");
            wprintf(L"  DOCLING_PYTHON        path to python.exe\n");
            wprintf(L"  DOCLING_TIMEOUT       seconds (0 = no limit)\n");
            wprintf(L"  PILLOW_MAX_IMAGE_PIXELS  large PNG limit (default %s)\n", DEFAULT_PILLOW);
            return 0;
        }
    }
    return 1;
}

static void load_config(void)
{
    ZeroMemory(&g, sizeof(g));
    g.doc_timeout_sec = DEFAULT_TIMEOUT;

    const wchar_t *pillow = _wgetenv(L"PILLOW_MAX_IMAGE_PIXELS");
    if (!pillow || !pillow[0]) pillow = DEFAULT_PILLOW;
    wcopy(g.pillow_pixels, pillow, 32);

    const wchar_t *to = _wgetenv(L"DOCLING_TIMEOUT");
    if (to && to[0]) g.doc_timeout_sec = _wtoi(to);

    wchar_t exe_dir[MAX_PATH_W];
    get_exe_dir(exe_dir, MAX_PATH_W);

    const wchar_t *root = _wgetenv(L"DOCLING_ROOT");
    if (root && root[0]) wcopy(g.root, root, MAX_PATH_W);
    else wcopy(g.root, exe_dir, MAX_PATH_W);

    path_join(g.docs, MAX_PATH_W, g.root, L"docs");
    path_join(g.parsed, MAX_PATH_W, g.root, L"parsed");
    path_join(g.logs, MAX_PATH_W, g.root, L"logs");
}

static void make_log_path(void)
{
    SYSTEMTIME st;
    GetLocalTime(&st);
    swprintf(g.log_path, MAX_PATH_W, L"%s\\run_%04u%02u%02u_%02u%02u%02u.log",
             g.logs, st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);
}

int wmain(int argc, wchar_t **argv)
{
    if (!AttachConsole(ATTACH_PARENT_PROCESS))
        AllocConsole();
    SetConsoleOutputCP(CP_UTF8);

    if (!parse_args(argc, argv))
        return 0;

    load_config();
    ensure_dir(g.docs);
    ensure_dir(g.parsed);
    ensure_dir(g.logs);
    make_log_path();

    g_log = _wfopen(g.log_path, L"w, ccs=UTF-8");
    if (!g_log) g_log = _wfopen(g.log_path, L"w");

    wprintf(L"Docling batch v%ls\n", VERSION);
    wprintf(L"root:   %s\n", g.root);
    wprintf(L"docs:   %s\n", g.docs);
    wprintf(L"parsed: %s\n", g.parsed);

    if (!find_python()) {
        say(L"ERROR: python.exe not found. Set DOCLING_PYTHON or install docling.");
        logf(L"ERROR python not found");
        if (g_log) fclose(g_log);
        return 1;
    }

    wprintf(L"python: %s\n", g.python);
    wprintf(L"log:    %s\n\n", g.log_path);

    logf(L"start v%ls", VERSION);
    logf(L"python=%s", g.python);
    logf(L"pillow=%s", g.pillow_pixels);

    scan_dir(g.docs);

    wprintf(L"\n---\n");
    wprintf(L"found:   %d\n", g.total);
    wprintf(L"parsed:  %d\n", g.done);
    wprintf(L"skipped: %d\n", g.skipped);
    wprintf(L"failed:  %d\n", g.failed);
    wprintf(L"log: %s\n", g.log_path);

    logf(L"done found=%d ok=%d skip=%d fail=%d",
         g.total, g.done, g.skipped, g.failed);

    if (g_log) fclose(g_log);
    return g.failed > 0 ? 1 : 0;
}
