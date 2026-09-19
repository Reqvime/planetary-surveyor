#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

FARPROC g_version_exports[17] = {0};

static HMODULE g_module = NULL;
static HMODULE g_real_version = NULL;
static const char g_loader_marker[] = "PDS_VERSION_LOADER_V1";
static const char g_shared_loader_marker[] = "PDS_LOADS_ALL_MODS_V1";

static const char *g_export_names[17] = {
    "GetFileVersionInfoA",
    "GetFileVersionInfoByHandle",
    "GetFileVersionInfoExA",
    "GetFileVersionInfoExW",
    "GetFileVersionInfoSizeA",
    "GetFileVersionInfoSizeExA",
    "GetFileVersionInfoSizeExW",
    "GetFileVersionInfoSizeW",
    "GetFileVersionInfoW",
    "VerFindFileA",
    "VerFindFileW",
    "VerInstallFileA",
    "VerInstallFileW",
    "VerLanguageNameA",
    "VerLanguageNameW",
    "VerQueryValueA",
    "VerQueryValueW",
};

static BOOL GetBinaryDirectory(wchar_t *buffer, DWORD count) {
    wchar_t *slash;
    if (!GetModuleFileNameW(g_module, buffer, count)) {
        return FALSE;
    }
    slash = wcsrchr(buffer, L'\\');
    if (!slash) {
        return FALSE;
    }
    *slash = L'\0';
    return TRUE;
}

static BOOL GetBundleRoot(wchar_t *buffer, DWORD count) {
    wchar_t binary_dir[MAX_PATH];
    wchar_t candidate[MAX_PATH];
    if (!GetBinaryDirectory(binary_dir, ARRAYSIZE(binary_dir))) {
        return FALSE;
    }
    _snwprintf_s(
        candidate,
        ARRAYSIZE(candidate),
        _TRUNCATE,
        L"%ls\\..\\PlanetaryDiscoveryScanner",
        binary_dir);
    return GetFullPathNameW(candidate, count, buffer, NULL) != 0;
}

static void AppendLog(const wchar_t *message, DWORD error) {
    wchar_t bundle_root[MAX_PATH];
    wchar_t log_dir[MAX_PATH];
    wchar_t log_path[MAX_PATH];
    SYSTEMTIME now;
    FILE *stream = NULL;

    if (!GetBundleRoot(bundle_root, ARRAYSIZE(bundle_root))) {
        return;
    }
    _snwprintf_s(log_dir, ARRAYSIZE(log_dir), _TRUNCATE, L"%ls\\logs", bundle_root);
    CreateDirectoryW(log_dir, NULL);
    _snwprintf_s(
        log_path,
        ARRAYSIZE(log_path),
        _TRUNCATE,
        L"%ls\\version-loader.log",
        log_dir);
    if (_wfopen_s(&stream, log_path, L"a+, ccs=UTF-8") != 0 || !stream) {
        return;
    }
    GetLocalTime(&now);
    fwprintf(
        stream,
        L"%04u-%02u-%02u %02u:%02u:%02u.%03u %ls error=%lu\n",
        now.wYear,
        now.wMonth,
        now.wDay,
        now.wHour,
        now.wMinute,
        now.wSecond,
        now.wMilliseconds,
        message,
        error);
    fclose(stream);
}

static BOOL LoadRealVersion(void) {
    wchar_t system_dir[MAX_PATH];
    wchar_t real_path[MAX_PATH];
    int index;

    if (!GetSystemDirectoryW(system_dir, ARRAYSIZE(system_dir))) {
        return FALSE;
    }
    _snwprintf_s(
        real_path,
        ARRAYSIZE(real_path),
        _TRUNCATE,
        L"%ls\\version.dll",
        system_dir);
    g_real_version = LoadLibraryW(real_path);
    if (!g_real_version) {
        return FALSE;
    }
    for (index = 0; index < ARRAYSIZE(g_export_names); ++index) {
        g_version_exports[index] = GetProcAddress(g_real_version, g_export_names[index]);
        if (!g_version_exports[index]) {
            return FALSE;
        }
    }
    return TRUE;
}

static BOOL LoadModModule(const wchar_t *binary_dir, const wchar_t *file_name) {
    wchar_t module_path[MAX_PATH];
    wchar_t message[MAX_PATH + 64];
    HMODULE module;
    DWORD error;

    if (_snwprintf_s(
            module_path,
            ARRAYSIZE(module_path),
            _TRUNCATE,
            L"%ls\\%ls",
            binary_dir,
            file_name) < 0) {
        AppendLog(L"module path is too long", ERROR_INSUFFICIENT_BUFFER);
        return FALSE;
    }
    module = LoadLibraryW(module_path);
    error = module ? ERROR_SUCCESS : GetLastError();
    _snwprintf_s(
        message,
        ARRAYSIZE(message),
        _TRUNCATE,
        module ? L"module loaded: %ls" : L"module load failed: %ls",
        file_name);
    AppendLog(message, error);
    return module != NULL;
}

static DWORD WINAPI LoadModModules(LPVOID parameter) {
    wchar_t binary_dir[MAX_PATH];
    wchar_t pattern[MAX_PATH];
    WIN32_FIND_DATAW find_data;
    HANDLE find_handle;
    DWORD loaded = 0;
    DWORD failed = 0;
    BOOL scanner_loaded;
    wchar_t summary[128];
    (void)parameter;

    Sleep(100);
    if (!GetBinaryDirectory(binary_dir, ARRAYSIZE(binary_dir))) {
        AppendLog(L"module path resolution failed", GetLastError());
        return 1;
    }

    scanner_loaded = LoadModModule(binary_dir, L"PlanetaryDiscoveryScanner.mods");
    if (scanner_loaded) {
        ++loaded;
    } else {
        ++failed;
    }

    if (_snwprintf_s(
            pattern,
            ARRAYSIZE(pattern),
            _TRUNCATE,
            L"%ls\\*.mods",
            binary_dir) < 0) {
        AppendLog(L"module search path is too long", ERROR_INSUFFICIENT_BUFFER);
        return scanner_loaded ? 0 : 2;
    }
    find_handle = FindFirstFileW(pattern, &find_data);
    if (find_handle == INVALID_HANDLE_VALUE) {
        AppendLog(L"module enumeration failed", GetLastError());
        return scanner_loaded ? 0 : 2;
    }
    do {
        if ((find_data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0 ||
            _wcsicmp(find_data.cFileName, L"PlanetaryDiscoveryScanner.mods") == 0) {
            continue;
        }
        if (LoadModModule(binary_dir, find_data.cFileName)) {
            ++loaded;
        } else {
            ++failed;
        }
    } while (FindNextFileW(find_handle, &find_data));
    FindClose(find_handle);

    _snwprintf_s(
        summary,
        ARRAYSIZE(summary),
        _TRUNCATE,
        L"module loading complete: loaded=%lu failed=%lu",
        loaded,
        failed);
    AppendLog(summary, 0);
    return scanner_loaded ? 0 : 2;
}

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        HANDLE thread;
        g_module = module;
        OutputDebugStringA(g_loader_marker);
        OutputDebugStringA(g_shared_loader_marker);
        DisableThreadLibraryCalls(module);
        if (!LoadRealVersion()) {
            return FALSE;
        }
        thread = CreateThread(NULL, 0, LoadModModules, NULL, 0, NULL);
        if (thread) {
            CloseHandle(thread);
        }
    }
    return TRUE;
}
