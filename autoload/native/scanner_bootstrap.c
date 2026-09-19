#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdarg.h>
#include <stdio.h>
#include <wchar.h>

#include "scanner_ui.h"

typedef int(__cdecl *RunFileFn)(const char *);

static HMODULE g_module = NULL;
static const char g_autoload_marker[] = "PDS_AUTOLOAD_MODULE_V1";

static BOOL GetBundleRoot(wchar_t *buffer, DWORD count) {
    wchar_t module_path[MAX_PATH];
    wchar_t candidate[MAX_PATH];
    wchar_t *slash;

    if (!GetModuleFileNameW(g_module, module_path, ARRAYSIZE(module_path))) {
        return FALSE;
    }
    slash = wcsrchr(module_path, L'\\');
    if (!slash) {
        return FALSE;
    }
    *slash = L'\0';
    if (_snwprintf_s(
            candidate,
            ARRAYSIZE(candidate),
            _TRUNCATE,
            L"%ls\\..\\PlanetaryDiscoveryScanner",
            module_path) < 0) {
        return FALSE;
    }
    return GetFullPathNameW(candidate, count, buffer, NULL) != 0;
}

static void AppendLog(const wchar_t *bundle_root, const wchar_t *format, ...) {
    wchar_t log_dir[MAX_PATH];
    wchar_t log_path[MAX_PATH];
    SYSTEMTIME now;
    FILE *stream = NULL;
    va_list args;

    if (!bundle_root) {
        return;
    }
    _snwprintf_s(log_dir, ARRAYSIZE(log_dir), _TRUNCATE, L"%ls\\logs", bundle_root);
    CreateDirectoryW(log_dir, NULL);
    _snwprintf_s(
        log_path,
        ARRAYSIZE(log_path),
        _TRUNCATE,
        L"%ls\\autoload-bootstrap.log",
        log_dir);
    if (_wfopen_s(&stream, log_path, L"a+, ccs=UTF-8") != 0 || !stream) {
        return;
    }

    GetLocalTime(&now);
    fwprintf(
        stream,
        L"%04u-%02u-%02u %02u:%02u:%02u.%03u ",
        now.wYear,
        now.wMonth,
        now.wDay,
        now.wHour,
        now.wMinute,
        now.wSecond,
        now.wMilliseconds);
    va_start(args, format);
    vfwprintf(stream, format, args);
    va_end(args);
    fputws(L"\n", stream);
    fclose(stream);
}

static BOOL IsSmokeTest(void) {
    wchar_t value[8];
    return GetEnvironmentVariableW(L"PDS_BOOTSTRAP_SMOKE", value, ARRAYSIZE(value)) > 0;
}

static BOOL IsNmsProcess(void) {
    wchar_t exe_path[MAX_PATH];
    wchar_t *name;
    if (!GetModuleFileNameW(NULL, exe_path, ARRAYSIZE(exe_path))) {
        return FALSE;
    }
    name = wcsrchr(exe_path, L'\\');
    name = name ? name + 1 : exe_path;
    return _wcsicmp(name, L"NMS.exe") == 0;
}

static DWORD BootstrapDelay(void) {
    wchar_t value[32];
    DWORD length = GetEnvironmentVariableW(
        L"PDS_BOOTSTRAP_DELAY_MS", value, ARRAYSIZE(value));
    if (length > 0 && length < ARRAYSIZE(value)) {
        wchar_t *end = NULL;
        unsigned long parsed = wcstoul(value, &end, 10);
        if (end && *end == L'\0' && parsed <= 60000UL) {
            return (DWORD)parsed;
        }
    }
    return 4000;
}

static DWORD WINAPI BootstrapThread(LPVOID parameter) {
    wchar_t bundle_root[MAX_PATH];
    wchar_t runtime[MAX_PATH];
    wchar_t python_dll[MAX_PATH];
    wchar_t runner_pyd[MAX_PATH];
    wchar_t bootstrap_py[MAX_PATH];
    wchar_t python_path[4 * MAX_PATH];
    char bootstrap_ansi[MAX_PATH * 2];
    HMODULE python = NULL;
    HMODULE runner = NULL;
    RunFileFn run_file = NULL;
    int result;
    (void)parameter;

    if (!GetBundleRoot(bundle_root, ARRAYSIZE(bundle_root))) {
        return 1;
    }
    OutputDebugStringA(g_autoload_marker);
    AppendLog(bundle_root, L"native module loaded marker=PDS_AUTOLOAD_MODULE_V1 pid=%lu", GetCurrentProcessId());

    if (!IsNmsProcess() && !IsSmokeTest()) {
        AppendLog(bundle_root, L"bootstrap skipped: host process is not NMS.exe");
        return 0;
    }

    Sleep(BootstrapDelay());
    if (IsNmsProcess()) {
        AppendLog(
            bundle_root,
            L"settings UI install result=%ls",
            InstallScannerSettingsUi(bundle_root) ? L"ok" : L"disabled");
    }
    _snwprintf_s(runtime, ARRAYSIZE(runtime), _TRUNCATE, L"%ls\\runtime", bundle_root);
    _snwprintf_s(
        python_dll,
        ARRAYSIZE(python_dll),
        _TRUNCATE,
        L"%ls\\python313.dll",
        runtime);
    _snwprintf_s(
        runner_pyd,
        ARRAYSIZE(runner_pyd),
        _TRUNCATE,
        L"%ls\\Lib\\site-packages\\pyrun_injected\\dll.cp313-win_amd64.pyd",
        runtime);
    _snwprintf_s(
        bootstrap_py,
        ARRAYSIZE(bootstrap_py),
        _TRUNCATE,
        L"%ls\\app\\autoload_bootstrap.py",
        bundle_root);
    _snwprintf_s(
        python_path,
        ARRAYSIZE(python_path),
        _TRUNCATE,
        L"%ls\\python313.zip;%ls;%ls\\Lib\\site-packages",
        runtime,
        runtime,
        runtime);

    SetEnvironmentVariableW(L"PDS_ROOT", bundle_root);
    SetEnvironmentVariableW(L"PYTHONHOME", runtime);
    SetEnvironmentVariableW(L"PYTHONPATH", python_path);
    SetEnvironmentVariableW(L"PYTEST_VERSION", L"1");

    python = LoadLibraryExW(python_dll, NULL, LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!python) {
        AppendLog(bundle_root, L"python313.dll load failed (error=%lu)", GetLastError());
        return 2;
    }
    AppendLog(bundle_root, L"python313.dll loaded");

    runner = LoadLibraryExW(runner_pyd, NULL, LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!runner) {
        AppendLog(bundle_root, L"pyrun runner load failed (error=%lu)", GetLastError());
        return 3;
    }
    run_file = (RunFileFn)GetProcAddress(runner, "run_file");
    if (!run_file) {
        AppendLog(bundle_root, L"pyrun run_file export missing (error=%lu)", GetLastError());
        return 4;
    }
    if (!WideCharToMultiByte(
            CP_ACP,
            0,
            bootstrap_py,
            -1,
            bootstrap_ansi,
            (int)sizeof(bootstrap_ansi),
            NULL,
            NULL)) {
        AppendLog(bundle_root, L"bootstrap path conversion failed (error=%lu)", GetLastError());
        return 5;
    }

    AppendLog(bundle_root, L"starting Python bootstrap");
    result = run_file(bootstrap_ansi);
    AppendLog(bundle_root, L"Python bootstrap returned result=%d", result);
    return result == 0 ? 0 : 6;
}

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        HANDLE thread;
        g_module = module;
        DisableThreadLibraryCalls(module);
        thread = CreateThread(NULL, 0, BootstrapThread, NULL, 0, NULL);
        if (thread) {
            CloseHandle(thread);
        }
    }
    return TRUE;
}
