option casemap:none

EXTERN g_version_exports:QWORD

.code

GetFileVersionInfoA PROC
    jmp QWORD PTR [g_version_exports + 0 * 8]
GetFileVersionInfoA ENDP

GetFileVersionInfoByHandle PROC
    jmp QWORD PTR [g_version_exports + 1 * 8]
GetFileVersionInfoByHandle ENDP

GetFileVersionInfoExA PROC
    jmp QWORD PTR [g_version_exports + 2 * 8]
GetFileVersionInfoExA ENDP

GetFileVersionInfoExW PROC
    jmp QWORD PTR [g_version_exports + 3 * 8]
GetFileVersionInfoExW ENDP

GetFileVersionInfoSizeA PROC
    jmp QWORD PTR [g_version_exports + 4 * 8]
GetFileVersionInfoSizeA ENDP

GetFileVersionInfoSizeExA PROC
    jmp QWORD PTR [g_version_exports + 5 * 8]
GetFileVersionInfoSizeExA ENDP

GetFileVersionInfoSizeExW PROC
    jmp QWORD PTR [g_version_exports + 6 * 8]
GetFileVersionInfoSizeExW ENDP

GetFileVersionInfoSizeW PROC
    jmp QWORD PTR [g_version_exports + 7 * 8]
GetFileVersionInfoSizeW ENDP

GetFileVersionInfoW PROC
    jmp QWORD PTR [g_version_exports + 8 * 8]
GetFileVersionInfoW ENDP

VerFindFileA PROC
    jmp QWORD PTR [g_version_exports + 9 * 8]
VerFindFileA ENDP

VerFindFileW PROC
    jmp QWORD PTR [g_version_exports + 10 * 8]
VerFindFileW ENDP

VerInstallFileA PROC
    jmp QWORD PTR [g_version_exports + 11 * 8]
VerInstallFileA ENDP

VerInstallFileW PROC
    jmp QWORD PTR [g_version_exports + 12 * 8]
VerInstallFileW ENDP

VerLanguageNameA PROC
    jmp QWORD PTR [g_version_exports + 13 * 8]
VerLanguageNameA ENDP

VerLanguageNameW PROC
    jmp QWORD PTR [g_version_exports + 14 * 8]
VerLanguageNameW ENDP

VerQueryValueA PROC
    jmp QWORD PTR [g_version_exports + 15 * 8]
VerQueryValueA ENDP

VerQueryValueW PROC
    jmp QWORD PTR [g_version_exports + 16 * 8]
VerQueryValueW ENDP

END
