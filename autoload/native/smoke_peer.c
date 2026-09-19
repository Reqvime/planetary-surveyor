#define WIN32_LEAN_AND_MEAN
#include <windows.h>

static const char g_smoke_marker[] = "PDS_SMOKE_PEER_V1";

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID reserved) {
    (void)module;
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        OutputDebugStringA(g_smoke_marker);
        SetEnvironmentVariableW(L"PDS_SMOKE_PEER_LOADED", L"1");
    }
    return TRUE;
}
