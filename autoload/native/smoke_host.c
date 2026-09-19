#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wchar.h>

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command_line, int show) {
    wchar_t library[MAX_PATH] = L"version.dll";
    HMODULE proxy;
    (void)instance;
    (void)previous;
    (void)command_line;
    (void)show;

    GetEnvironmentVariableW(L"PDS_SMOKE_LIBRARY", library, ARRAYSIZE(library));
    proxy = LoadLibraryW(library);
    if (!proxy) {
        return 10;
    }
    if (_wcsicmp(library, L"version.dll") == 0) {
        typedef DWORD(WINAPI *GetVersionSizeFn)(LPCWSTR, LPDWORD);
        wchar_t system_dir[MAX_PATH];
        wchar_t kernel_path[MAX_PATH];
        DWORD ignored = 0;
        GetVersionSizeFn get_size =
            (GetVersionSizeFn)GetProcAddress(proxy, "GetFileVersionInfoSizeW");
        if (!get_size || !GetSystemDirectoryW(system_dir, ARRAYSIZE(system_dir))) {
            return 12;
        }
        _snwprintf_s(
            kernel_path,
            ARRAYSIZE(kernel_path),
            _TRUNCATE,
            L"%ls\\kernel32.dll",
            system_dir);
        if (get_size(kernel_path, &ignored) == 0) {
            return 13;
        }
    }
    Sleep(5000);
    if (GetEnvironmentVariableW(L"PDS_SMOKE_EXPECT_PEER", NULL, 0) != 0 &&
        GetEnvironmentVariableW(L"PDS_SMOKE_PEER_LOADED", NULL, 0) == 0) {
        return 14;
    }
    return 0;
}
