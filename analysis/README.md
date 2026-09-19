# Static analysis

В Git хранятся только воспроизводимые Ghidra scripts. Сам проект Ghidra, копия
`NMS.exe`, декомпиляция и отчёты остаются локальными и не коммитятся.

- `InspectPopulateDiscoveryInfo.java` находит официальную сигнатуру populate,
  перечисляет прямые вызовы и декомпилирует функцию.
- `InspectFunctionsByAddress.java` выводит entry bytes, callers, direct callees и
  декомпиляцию для заданных VA.

Результаты для `NMS.exe` 178938 перенесены в `docs/findings.md`. Эти адреса и
сигнатуры нельзя автоматически переносить на следующий build игры.
