#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

#include "scanner_ui.h"

typedef void (*AddSectionHeaderFn)(void *, const char *, int);
typedef unsigned char (*AddToggleOptionFn)(
    void *, const char *, const char *, unsigned char, unsigned char, const char **);
typedef int (*AddIntSliderFn)(
    void *, const char *, const char *, int, int, int, int, const void *);

typedef struct SliderFormat {
    int step;
    int display_multiplier;
    const char *suffix;
    const void *formatter;
} SliderFormat;

typedef struct Pattern {
    const unsigned char *bytes;
    const char *mask;
    size_t length;
} Pattern;

static AddSectionHeaderFn g_add_section = NULL;
static AddToggleOptionFn g_add_toggle = NULL;
static AddIntSliderFn g_add_slider = NULL;
static wchar_t g_config_path[MAX_PATH];
static wchar_t g_log_path[MAX_PATH];
static volatile LONG g_render_fault_logged = 0;

static const char *g_toggle_labels[] = {"UI_ENABLED", "UI_DISABLED"};
static const SliderFormat g_delay_format = {1, 250, " ms", NULL};
static const SliderFormat g_key_format = {1, 1, "", NULL};

static const unsigned char g_section_bytes[] = {
    0x48, 0x89, 0x5C, 0x24, 0x10, 0x57, 0x48, 0x83, 0xEC, 0x40,
    0x83, 0x79, 0x08, 0x01, 0x48, 0x8B, 0xDA, 0x49, 0x63, 0xF8, 0x75,
};
static const unsigned char g_toggle_bytes[] = {
    0x4C, 0x89, 0x44, 0x24, 0x18, 0x56, 0x57, 0x41, 0x55, 0x41, 0x57,
    0x48, 0x83, 0xEC, 0x78, 0x83, 0x79, 0x08, 0x01, 0x41, 0x0F, 0xB6, 0xF9,
};
static const unsigned char g_slider_bytes[] = {
    0x44, 0x89, 0x4C, 0x24, 0x20, 0x4C, 0x89, 0x44, 0x24, 0x18, 0x55,
    0x56, 0x41, 0x57, 0x48, 0x8D, 0x6C, 0x24, 0xD9, 0x48, 0x81, 0xEC,
    0xE0, 0x00, 0x00, 0x00, 0x83, 0x79, 0x08, 0x01,
};
static const unsigned char g_callsite_bytes[] = {
    0x41, 0xB8, 0x02, 0x00, 0x00, 0x00, 0x48, 0x8D, 0x15,
    0x00, 0x00, 0x00, 0x00, 0x48, 0x8B, 0xCB, 0xE8,
    0x00, 0x00, 0x00, 0x00,
};

static void UiLog(const wchar_t *message) {
    FILE *stream = NULL;
    SYSTEMTIME now;
    if (!g_log_path[0]) {
        return;
    }
    if (_wfopen_s(&stream, g_log_path, L"a+, ccs=UTF-8") != 0 || !stream) {
        return;
    }
    GetLocalTime(&now);
    fwprintf(
        stream,
        L"%04u-%02u-%02u %02u:%02u:%02u.%03u %ls\n",
        now.wYear,
        now.wMonth,
        now.wDay,
        now.wHour,
        now.wMinute,
        now.wSecond,
        now.wMilliseconds,
        message);
    fclose(stream);
}

static void UiLogAddress(const wchar_t *name, const void *address) {
    wchar_t line[160];
    _snwprintf_s(line, ARRAYSIZE(line), _TRUNCATE, L"%ls=%p", name, address);
    UiLog(line);
}

static unsigned char *FindUnique(
    unsigned char *start, size_t size, const Pattern *pattern) {
    unsigned char *found = NULL;
    size_t offset;
    size_t index;
    if (pattern->length == 0 || size < pattern->length) {
        return NULL;
    }
    for (offset = 0; offset <= size - pattern->length; ++offset) {
        for (index = 0; index < pattern->length; ++index) {
            if (pattern->mask[index] == 'x' &&
                start[offset + index] != pattern->bytes[index]) {
                break;
            }
        }
        if (index == pattern->length) {
            if (found) {
                return NULL;
            }
            found = start + offset;
        }
    }
    return found;
}

static BOOL GetTextSection(unsigned char **start, size_t *size) {
    unsigned char *base = (unsigned char *)GetModuleHandleW(NULL);
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS64 *nt;
    IMAGE_SECTION_HEADER *section;
    WORD index;
    if (!base) {
        return FALSE;
    }
    dos = (IMAGE_DOS_HEADER *)base;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) {
        return FALSE;
    }
    nt = (IMAGE_NT_HEADERS64 *)(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) {
        return FALSE;
    }
    section = IMAGE_FIRST_SECTION(nt);
    for (index = 0; index < nt->FileHeader.NumberOfSections; ++index, ++section) {
        if (memcmp(section->Name, ".text", 5) == 0) {
            *start = base + section->VirtualAddress;
            *size = section->Misc.VirtualSize;
            return TRUE;
        }
    }
    return FALSE;
}

static int ReadInt(const wchar_t *name, int fallback, int minimum, int maximum) {
    int value = (int)GetPrivateProfileIntW(L"Scanner", name, fallback, g_config_path);
    if (value < minimum) {
        return minimum;
    }
    if (value > maximum) {
        return maximum;
    }
    return value;
}

static unsigned char ReadBool(const wchar_t *name, unsigned char fallback) {
    wchar_t value[16];
    GetPrivateProfileStringW(
        L"Scanner", name, fallback ? L"true" : L"false", value, ARRAYSIZE(value),
        g_config_path);
    return (unsigned char)(
        _wcsicmp(value, L"true") == 0 || _wcsicmp(value, L"yes") == 0 ||
        _wcsicmp(value, L"on") == 0 || wcstol(value, NULL, 10) != 0);
}

static unsigned char ReadAllMode(void) {
    wchar_t value[32];
    GetPrivateProfileStringW(
        L"Scanner", L"Mode", L"All", value, ARRAYSIZE(value), g_config_path);
    return (unsigned char)(_wcsicmp(value, L"FaunaOnly") != 0 &&
                           _wcsicmp(value, L"Fauna") != 0);
}

static int ReadScanKey(void) {
    wchar_t value[16];
    wchar_t *end = NULL;
    long parsed;
    GetPrivateProfileStringW(
        L"Scanner", L"ScanKey", L"F10", value, ARRAYSIZE(value), g_config_path);
    if (value[0] != L'F' && value[0] != L'f') {
        return 8;
    }
    parsed = wcstol(value + 1, &end, 10);
    if (!end || *end != L'\0' || parsed < 1 || parsed > 12) {
        return 8;
    }
    return (int)parsed;
}

static void WriteText(const wchar_t *name, const wchar_t *value) {
    if (!WritePrivateProfileStringW(L"Scanner", name, value, g_config_path)) {
        UiLog(L"settings write failed");
    }
}

static void WriteBool(const wchar_t *name, unsigned char value) {
    WriteText(name, value ? L"true" : L"false");
}

static void WriteInt(const wchar_t *name, int value) {
    wchar_t text[24];
    _snwprintf_s(text, ARRAYSIZE(text), _TRUNCATE, L"%d", value);
    WriteText(name, text);
}

static void RenderScannerSettings(void *menu) {
    unsigned char old_bool;
    unsigned char new_bool;
    int old_value;
    int new_value;
    wchar_t key_text[8];

    g_add_section(menu, "PLANETARY SURVEYOR", 2);

    old_bool = ReadAllMode();
    new_bool = g_add_toggle(
        menu,
        "INCLUDE FLORA AND MINERALS",
        "Off scans fauna only; on also attempts flora and minerals",
        old_bool,
        0,
        g_toggle_labels);
    if (new_bool != old_bool) {
        WriteText(L"Mode", new_bool ? L"All" : L"FaunaOnly");
        UiLog(new_bool ? L"Mode changed to All" : L"Mode changed to FaunaOnly");
    }

    old_value = (ReadInt(L"SubmitDelayMs", 500, 250, 1500) + 125) / 250;
    new_value = g_add_slider(
        menu,
        "PROCESSING DELAY",
        "Lower is faster; 500 ms is the recommended default",
        old_value,
        2,
        1,
        6,
        &g_delay_format);
    if (new_value != old_value) {
        WriteInt(L"SubmitDelayMs", new_value * 250);
        UiLog(L"SubmitDelayMs changed");
    }

    old_bool = ReadBool(L"SoundFeedback", 1);
    new_bool = g_add_toggle(
        menu,
        "DISCOVERY SOUND",
        "Play the discovery sound for every accepted entry",
        old_bool,
        0,
        g_toggle_labels);
    if (new_bool != old_bool) {
        WriteBool(L"SoundFeedback", new_bool);
        UiLog(L"SoundFeedback changed");
    }

    old_bool = ReadBool(L"EnableHotkey", 1);
    new_bool = g_add_toggle(
        menu,
        "ENABLE SCANNER HOTKEY",
        "Allow the configured F-key to start a planet scan",
        old_bool,
        0,
        g_toggle_labels);
    if (new_bool != old_bool) {
        WriteBool(L"EnableHotkey", new_bool);
        UiLog(L"EnableHotkey changed");
    }

    old_value = ReadScanKey();
    new_value = g_add_slider(
        menu,
        "SCAN KEY (F1-F12; RESTART REQUIRED)",
        "Choose the F-key number; restart the game to apply it",
        old_value,
        8,
        1,
        12,
        &g_key_format);
    if (new_value != old_value) {
        _snwprintf_s(key_text, ARRAYSIZE(key_text), _TRUNCATE, L"F%d", new_value);
        WriteText(L"ScanKey", key_text);
        UiLog(L"ScanKey changed; restart required");
    }
}

static void HookedSectionHeader(void *menu, const char *label, int style) {
    if (InterlockedCompareExchange(&g_render_fault_logged, 0, 0) == 0) {
        __try {
            RenderScannerSettings(menu);
        }
        __except (EXCEPTION_EXECUTE_HANDLER) {
            if (InterlockedCompareExchange(&g_render_fault_logged, 1, 0) == 0) {
                UiLog(L"settings render disabled after exception");
            }
        }
    }
    /* Restore the game's original first section after our complete section. */
    g_add_section(menu, label, style);
}

static void *AllocateRelayNear(const void *target) {
    SYSTEM_INFO system_info;
    MEMORY_BASIC_INFORMATION memory;
    uintptr_t center = (uintptr_t)target;
    uintptr_t minimum;
    uintptr_t maximum;
    uintptr_t cursor;
    uintptr_t candidate;
    uintptr_t region_end;
    void *relay;

    GetSystemInfo(&system_info);
    minimum = center > 0x70000000ULL ? center - 0x70000000ULL :
        (uintptr_t)system_info.lpMinimumApplicationAddress;
    maximum = center + 0x70000000ULL;
    if (maximum > (uintptr_t)system_info.lpMaximumApplicationAddress) {
        maximum = (uintptr_t)system_info.lpMaximumApplicationAddress;
    }
    cursor = minimum;
    while (cursor < maximum && VirtualQuery((void *)cursor, &memory, sizeof(memory))) {
        region_end = (uintptr_t)memory.BaseAddress + memory.RegionSize;
        if (memory.State == MEM_FREE) {
            candidate = ((uintptr_t)memory.BaseAddress +
                         system_info.dwAllocationGranularity - 1) &
                        ~((uintptr_t)system_info.dwAllocationGranularity - 1);
            if (candidate < maximum && candidate + 64 <= region_end) {
                relay = VirtualAlloc(
                    (void *)candidate,
                    64,
                    MEM_COMMIT | MEM_RESERVE,
                    PAGE_EXECUTE_READWRITE);
                if (relay) {
                    return relay;
                }
            }
        }
        if (region_end <= cursor) {
            break;
        }
        cursor = region_end;
    }
    return NULL;
}

static BOOL PatchCall(
    unsigned char *call_instruction, AddSectionHeaderFn destination) {
    unsigned char *relay;
    unsigned char relay_code[12] = {0x48, 0xB8, 0, 0, 0, 0, 0, 0, 0, 0, 0xFF, 0xE0};
    int64_t displacement;
    int32_t relative;
    DWORD old_protect;
    DWORD restored;

    relay = (unsigned char *)AllocateRelayNear(call_instruction);
    if (!relay) {
        UiLog(L"unable to allocate near relay");
        return FALSE;
    }
    memcpy(relay_code + 2, &destination, sizeof(destination));
    memcpy(relay, relay_code, sizeof(relay_code));
    FlushInstructionCache(GetCurrentProcess(), relay, sizeof(relay_code));

    displacement = (int64_t)(relay - (call_instruction + 5));
    if (displacement < INT32_MIN || displacement > INT32_MAX) {
        UiLog(L"near relay is outside rel32 range");
        return FALSE;
    }
    relative = (int32_t)displacement;
    if (!VirtualProtect(call_instruction, 5, PAGE_EXECUTE_READWRITE, &old_protect)) {
        UiLog(L"callsite VirtualProtect failed");
        return FALSE;
    }
    call_instruction[0] = 0xE8;
    memcpy(call_instruction + 1, &relative, sizeof(relative));
    FlushInstructionCache(GetCurrentProcess(), call_instruction, 5);
    VirtualProtect(call_instruction, 5, old_protect, &restored);
    return TRUE;
}

BOOL InstallScannerSettingsUi(const wchar_t *bundle_root) {
    static const Pattern section_pattern = {
        g_section_bytes, "xxxxxxxxxxxxxxxxxxxxx", sizeof(g_section_bytes)};
    static const Pattern toggle_pattern = {
        g_toggle_bytes, "xxxxxxxxxxxxxxxxxxxxxxx", sizeof(g_toggle_bytes)};
    static const Pattern slider_pattern = {
        g_slider_bytes, "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", sizeof(g_slider_bytes)};
    static const Pattern callsite_pattern = {
        g_callsite_bytes, "xxxxxxxxx????xxxx????", sizeof(g_callsite_bytes)};
    unsigned char *text;
    size_t text_size;
    unsigned char *section;
    unsigned char *toggle;
    unsigned char *slider;
    unsigned char *cursor;
    unsigned char *callsite = NULL;
    size_t remaining;
    int32_t relative;
    unsigned char *target;
    int matches = 0;
    wchar_t log_dir[MAX_PATH];

    _snwprintf_s(log_dir, ARRAYSIZE(log_dir), _TRUNCATE, L"%ls\\logs", bundle_root);
    CreateDirectoryW(log_dir, NULL);
    _snwprintf_s(
        g_log_path, ARRAYSIZE(g_log_path), _TRUNCATE, L"%ls\\settings-ui.log", log_dir);
    _snwprintf_s(
        g_config_path,
        ARRAYSIZE(g_config_path),
        _TRUNCATE,
        L"%ls\\..\\Binaries\\PlanetaryDiscoveryScanner.ini",
        bundle_root);
    UiLog(L"resolving native Options UI");

    if (!GetTextSection(&text, &text_size)) {
        UiLog(L"NMS .text section unavailable; UI disabled");
        return FALSE;
    }
    section = FindUnique(text, text_size, &section_pattern);
    toggle = FindUnique(text, text_size, &toggle_pattern);
    slider = FindUnique(text, text_size, &slider_pattern);
    if (!section || !toggle || !slider) {
        UiLog(L"Options functions unresolved; UI disabled");
        return FALSE;
    }

    cursor = text;
    remaining = text_size;
    while (remaining >= callsite_pattern.length) {
        unsigned char *candidate = NULL;
        size_t offset;
        size_t index;
        for (offset = 0; offset <= remaining - callsite_pattern.length; ++offset) {
            for (index = 0; index < callsite_pattern.length; ++index) {
                if (callsite_pattern.mask[index] == 'x' &&
                    cursor[offset + index] != callsite_pattern.bytes[index]) {
                    break;
                }
            }
            if (index == callsite_pattern.length) {
                candidate = cursor + offset;
                break;
            }
        }
        if (!candidate) {
            break;
        }
        memcpy(&relative, candidate + 17, sizeof(relative));
        target = candidate + 21 + relative;
        if (target == section) {
            callsite = candidate + 16;
            ++matches;
        }
        remaining -= (size_t)(candidate + 1 - cursor);
        cursor = candidate + 1;
    }
    if (matches != 1 || !callsite || callsite[0] != 0xE8) {
        UiLog(L"safe Options callsite unresolved; UI disabled");
        return FALSE;
    }

    g_add_section = (AddSectionHeaderFn)section;
    g_add_toggle = (AddToggleOptionFn)toggle;
    g_add_slider = (AddIntSliderFn)slider;
    UiLogAddress(L"AddSectionHeader", section);
    UiLogAddress(L"AddToggleOption", toggle);
    UiLogAddress(L"AddIntSlider", slider);
    UiLogAddress(L"Options callsite", callsite);
    if (!PatchCall(callsite, HookedSectionHeader)) {
        UiLog(L"Options hook installation failed; UI disabled");
        return FALSE;
    }
    UiLog(L"Options hook live");
    return TRUE;
}
