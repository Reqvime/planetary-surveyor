#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wchar.h>

#ifdef PDS_UNINSTALL
static const wchar_t *g_command = L"uninstall";
#else
static const wchar_t *g_command = L"install";
#endif

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR arguments, int show) {
    wchar_t bundle[MAX_PATH];
    wchar_t python[MAX_PATH];
    wchar_t script[MAX_PATH];
    wchar_t command_line[4 * MAX_PATH];
    wchar_t *slash;
    STARTUPINFOW startup = {0};
    PROCESS_INFORMATION process = {0};
    DWORD exit_code = 1;
    (void)instance;
    (void)previous;
    (void)arguments;
    (void)show;

    if (!GetModuleFileNameW(NULL, bundle, ARRAYSIZE(bundle))) {
        return 2;
    }
    slash = wcsrchr(bundle, L'\\');
    if (!slash) {
        return 3;
    }
    *slash = L'\0';
    _snwprintf_s(
        python,
        ARRAYSIZE(python),
        _TRUNCATE,
        L"%ls\\runtime\\pythonw.exe",
        bundle);
    _snwprintf_s(
        script,
        ARRAYSIZE(script),
        _TRUNCATE,
        L"%ls\\app\\autoload_installer.py",
        bundle);
    _snwprintf_s(
        command_line,
        ARRAYSIZE(command_line),
        _TRUNCATE,
        L"\"%ls\" \"%ls\" %ls",
        python,
        script,
        g_command);

    startup.cb = sizeof(startup);
    if (!CreateProcessW(
            python,
            command_line,
            NULL,
            NULL,
            FALSE,
            CREATE_NO_WINDOW,
            NULL,
            bundle,
            &startup,
            &process)) {
        MessageBoxW(
            NULL,
            L"The bundled installer runtime could not be started. Re-extract the complete archive.",
            L"Planetary Discovery Scanner",
            MB_ICONERROR);
        return 4;
    }
    WaitForSingleObject(process.hProcess, INFINITE);
    GetExitCodeProcess(process.hProcess, &exit_code);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return (int)exit_code;
}
