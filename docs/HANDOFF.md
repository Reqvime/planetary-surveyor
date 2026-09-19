# NMSDiscoveryLab handoff

Этот файл предназначен для другого coding-agent, который продолжит проект без
повторения уже выполненного reverse engineering.

## AUTOLOAD ПОДТВЕРЖДЁН (2026-09-15 18:09 MSK)

Обычный запуск Steam без консоли подтверждён: существующий NoMansTime
`version.dll` загрузил `Binaries\PlanetaryDiscoveryScanner.mods`, тот поднял
bundled CPython 3.13.15 и pyMHF/NMS.py из `PlanetaryDiscoveryScanner`. Чистый
лог `pymhf-20260915T174122.log`: 3 mods / 6 hooks, `GameAddressesResolved=ok`,
F8 принял 30/30 (`Animal:3, Flora:15, Mineral:12`). Первый прототип вычислял
root как cwd/GAMEDATA; исправлено поиском `runtime\python313.zip` в `sys.path`.

Добавлены собственный 17-export `version.dll` forwarder, native GUI wrappers
install/uninstall и безопасная логика: существующий loader с `*.mods` не
заменяется, при его отсутствии ставится наш, несовместимый loader блокирует
установку. Собственный loader проверен в реальном Steam NMS без NoMansTime:
`pymhf-20260915T180541.log` содержит 3 mods / 6 hooks,
`GameAddressesResolved result=ok`; на второй планете очередь приняла 38/38
(`Animal:4, Flora:24, Mineral:10`) без submit failures.

## РЕШЕНИЕ О ПЕРВОМ ПУБЛИЧНОМ РЕЛИЗЕ (2026-09-15 16:50 MSK)

Пользователь проверил portable-запуск на `NMS.exe` 178994 и решил выпускать
текущую реализацию как beta, не задерживая релиз ради идеальной Flora/Mineral.
Последний лог `logs/pymhf-20260915T164851.log`: адреса разрешены успешно,
`spawn_arrays=12/61/57`, очередь приняла 52/52 без отказов
(`Animal:9, Flora:25, Mineral:18`). Пользователь подтвердил, что fauna работает,
но часть flora/minerals всё ещё может не засчитываться интерфейсом. Публичное
обещание: fauna — основная надёжная функция; flora/minerals — best effort.

## Релизные пакеты v1.1.0

`scripts/build-release.ps1` собирает пять архивов в `dist/`:

- `…-v1.1.0-Manual.zip` — основной публичный пакет без запуска установщика/CMD:
  готовая структура game root, а `version.dll` лежит отдельно и копируется
  только если такого файла ещё нет.
- `…-v1.1.0-Autoload.zip` — дополнительный GUI-вариант с автоматической
  проверкой конфликтов, затем обычный запуск Steam/Epic.
- `…-v1.1.0-Portable.zip` — резервный вариант. Папка
  `PlanetaryDiscoveryScanner/` кладётся рядом с `Binaries`; внутри официальный
  embeddable CPython 3.13.15 (`runtime/`, `python313._pth` дополнен
  `Lib\site-packages` и `import site` ради `pywin32.pth`), site-packages из
  `.venv` без pip/`__pycache__`, лаунчер `app/scanner.py` (play/uninstall/backup)
  и три `.cmd` без PowerShell. `play` копирует мод в mod_dir из существующего
  `pymhf.local.toml` или, если настроек нет, создаёт их с маркером
  `# Created by Planetary Discovery Scanner` (uninstall удаляет только такой файл)
  и запускает `pymhf run nmspy` in-process. Проверка длины пути (DLL не грузятся
  при пути ≥ 260 символов).
- `…-v1.1.0-MODS.zip` — две `.py` для тех, у кого NMS.py уже есть.
- `…-v1.1.0.zip` — developer/source пакет с `INSTALL.cmd` и строгим preflight.

Embeddable Python для сборки: `dist/cache/python-3.13.15-embed-amd64.zip`
(python.org, 11 009 825 байт, SHA256 `D1F04D99…A2CF`, подпись PSF валидна);
`dist/` не в git. Офлайн-тест в поддельной папке игры прошёл (install,
идемпотентность, backup, uninstall, ошибка вне папки игры, CRLF). В игре
портативный запуск ещё не проверялся: при `import pymhf` questionary строит
вопросы и требует настоящую консоль — `.cmd` её даёт, запуск без консоли падает.

## ОБНОВЛЕНИЕ 2026-09-15 ночь: v1.1.0 без hard-coded адресов

Первый запуск порта на 178994 (`logs/pymhf-20260915T145457.log`) ничего не
отправил: самопроверка `BuildLayoutCheck` сравнила байты SubmitDiscoveryData в
памяти, а там стоял detour собственного диагностического hook мода
(`observe_submit`) → ложный `SubmitDiscoveryData_signature_mismatch`, submit
заблокирован (save не менялся). Параллельно был запущен сторонний
`NMS Trainer.exe` — на результат не повлиял (стартовал позже проверки).

v1.1.0:

- RVA функций и application-data pointer больше не хранятся. Первый F8
  (`_resolve_game_addresses`) читает `.text` NMS.exe из памяти, ищет три
  сигнатуры (SubmitDiscoveryData, PostSubmitDiscovery, IsDiscoveryKnown) с
  проверкой уникальности; если пролог перехвачен (`E9 rel32`), повторяет поиск с
  wildcard первых 5 байт. Pointer декодируется из `mov rcx,[rip+disp]`
  IsDiscoveryKnown и обязан лежать внутри образа. Лог:
  `event=GameAddressesResolved result=ok submit_rva=… elapsed_seconds=…`
  (офлайн-замер на exe: 20–70 мс на сигнатуру).
- Удалены диагностические hooks `observe_submit`/`observe_populate` (спам
  тысяч строк при загрузке и причина ложной блокировки), мёртвые
  `_read_scene_snapshot`/`_read_player_position` со stale адресами.
- Timestamp открытия = `int(time.time())` (игра использует `_time64(NULL)`).
- `run.ps1`/`deploy.ps1`: несовпадение версии — warning, обязательны только
  используемые сигнатуры.
- `build-release.ps1` собирает полный пакет и drop-in
  `…-v1.1.0-MODS.zip` (две `.py` + `PlanetaryDiscoveryScanner-README.txt`).
- 21 tests OK, включая резолв сигнатур по установленному `..\Binaries\NMS.exe`.
- Ещё не проверено в игре: первым делом искать в логе
  `GameAddressesResolved result=ok`.

## ОБНОВЛЕНИЕ 2026-09-15 вечер: первый runtime F8 v2 и порт на 178994

Runtime `logs/pymhf-20260915T063417.log` (F8 v2, ещё build 178938):

- UA `9065477538783491`: Flora 10, Mineral 14 — все в save, пользователь
  подтвердил полные счётчики;
- UA `22576276420894979` (планета 5 старой системы): F8 v2 приняла 9
  (`Flora:3, Mineral:6`), отказов 0. Квест показывает **Minerals 22/23**.
  Каталог содержит 22 Mineral, все 22 в save; в save ещё два не-каталожных
  Mineral от F8 v1: STEAMVENT `A973434BBC291F83` и SMALLROCK
  `E6FA4A5526396511:7E1286D4BCAF9675`. Значит, одного ожидаемого минерала нет в
  трёх spawn-массивах/каталоге (вероятно, scene без прямого entity, как
  FISHFIENDROCK). Для диагностики F8 теперь логирует
  `PlanetObjectCatalogUnclassifiedScene` — повторный F8 на этой планете даст
  список кандидатов. Ключи вслепую не отправлять.
- Райская UA `18072676793524483` с F8 v2 ещё не проверялась.

Затем Steam обновил игру до `NMS.exe` 178994 (build 25320008); лаунчер
корректно остановился. Порт выполнен (см. «Build-specific адреса 178994»):
20 tests OK, включая сверку адресов с установленным exe; deploy SHA256 probe
`A1246EB5DB6FAE51AC85B3ACDFFCB319D22302670313EDDD66C80B8DA346E984`;
`run.ps1 -PreflightOnly` проходит. В игре 178994 ещё не запускалось — первым
делом проверить в логе `event=BuildLayoutCheck result=ok`.

## КРИТИЧЕСКОЕ СОСТОЯНИЕ НА 2026-09-15 (сессия Claude, игра закрыта)

Корень `Minerals 17/18` найден, F8 переведён на точный источник Flora/Mineral,
17 unit-тестов проходят, plugin задеплоен в `GAMEDATA\MODS` (SHA256 probe
`BCB64A08EEB71D34C4CAFE0EB47F1772778CF8E29C8B7A0643BB8A798FAB02EE`, catalogue
`CA2DC7C76B48FC40F79247924C9E6B75B5222F8EC4F084291852CE6661327254`).
**Нет runtime-подтверждения в игре** — до него не собирать zip и не считать
релиз готовым. Всё ниже в разделе «Архив» — прежнее состояние Codex; его
гипотеза про DECORATIVEGRAVELPATCH/Alt-Tab опровергнута.

### Причина 17/18 (UA 4561877911412995)

Сравнение save со spawn-таблицами планеты (ниже) дало точный ответ:

- лишняя запись: `STEAMVENT` `3558F0A7E83A4C51:CDB6CF21B532CF10`. Классификатор
  считал любой property `DiscoveryType` типом открытия; настоящий компонент —
  `GcEncyclopediaComponentData.Type`. У STEAMVENT Mineral пришёл только из
  `ScanIcon` дочерней `GEM.ENTITY`; Discoveries эту запись не считает;
- недостающая запись: `FISHFIENDROCK` `6972090063531EBE:E68FD63426773658`
  (array `+0x3C18`, slot 51). Scene не прикрепляет entity напрямую (вложенная
  `FISHFIENDROCKPARTS/FIENDROCKNEST.SCENE.MBIN` не распакована), поэтому
  классификатор её пропускал. Штатный resolver выдал её как Mineral
  (`logs/pymhf-20260914T092106.log`, UA 4747691344427360), а на планете
  UA 18072676793524483 она входит в знаменатель квеста 23;
- обе записи DECORATIVEGRAVELPATCH (`106E681A1BFCEDF2`, `9569667AF122177C`)
  лежат в spawn-таблице этой планеты (array `+0x3C28`, slots 34 и 36) и
  засчитываются: счётчик вырос 15 → 17 при двух записях с seed `9569…`.

Итого 18 records = 17 настоящих + STEAMVENT; 18-й настоящий (FISHFIENDROCK)
отсутствовал.

### Точный источник Flora/Mineral (реализован)

Внутри inline-планеты `cGcSolarSystem` (та же структура, что для fauna; offsets
от начала планеты, **не** от planet data `+0x60`) лежат три spawn-массива:
`+0x3C08`, `+0x3C18`, `+0x3C28`. Перед каждым указателем на элементы:
`u32 capacity` (`-8`) и `u32 size` (`-4`); длины совпали с независимым
signature-дампом. Элемент `0x70` байт: filename VariableString ptr `+0x18`,
u32 length `+0x20` (старшие байты qword — мусор), seed `+0x38`, use-seed flag
`+0x40`. Таблицы сохраняются для всех планет, посещённых в текущем процессе.

Read-only проверка на живом процессе:

| планета | размеры массивов | Flora | Mineral | игра |
|---|---|---|---|---|
| UA 4561877911412995 | 11/63/62 | 27 + 5 landmark = 32 | 18 | UI 32/32, x/18 |
| UA 18072676793524483 | 10/63/75 | 26 | 23 | квест Flora 8/21, Minerals 15/23 |

Minerals совпадают точно. Flora на второй планете — надмножество: 26 против 21
(игра не считает 5 записей каталога и одну уже известную; вероятный кандидат
CLAMSHELL, правило не доказано). Лишние records безвредны для счётчика (как
14 Animal records при 13/13), поэтому F8 отправляет надмножество.

### Что изменено в коде

- `src/discovery_probe.py`: `_read_planet_object_catalog(planet, UA)` читает
  три массива вместо эвристики кластеров `cTkResourceManager::mResources`;
  кластерные функции и `_RESOURCE_*` удалены. Слоты без use-seed
  пропускаются; нечитаемые имена считаются как `invalid` и пропускаются. Лог:
  `PlanetObjectCatalogReady spawn_arrays=… matching=… unseeded=… invalid=… entries=…`.
- Focus guard: paced submit стоит на паузе, пока foreground window не
  принадлежит NMS.exe (`PlanetDiscoverySubmitPaused/Resumed`, `focus_pauses`
  в `NearbyDiscoverySubmitEnd`); после возврата фокуса ждёт один интервал.
- `analysis/build_stage9_scene_types.py`: `SCENE_TYPE_OVERRIDES` (STEAMVENT
  исключён, FISHFIENDROCK = Mineral). `src/planet_object_types.py`
  перегенерирован: 192 Flora / 188 Mineral, дельта ровно эти две scene. Вне
  Codex генератору нужен
  `LOCALAPPDATA`, указывающий на виртуализированный `%LOCALAPPDATA%` Codex
  (`...\Packages\OpenAI.Codex_*\LocalCache\Local`).
- Тесты: `tests/test_planet_object_catalog.py` (layout, overrides, dedupe,
  use-seed, invalid name, size>capacity, пустые массивы, focus guard); старые
  кластерные тесты удалены.
- Прежние deployed-файлы сохранены вне проекта в scratchpad сессии Claude
  (`backup_before_f8v2\deployed`), SHA256 probe `14112A6E…`.

### Следующий runtime-тест

1. Запуск через `PLAY_NMS_WITH_SCANNER.cmd`, стоять на райской планете
   UA `18072676793524483` (квест «Руководство по исследованию»: Flora 8/21,
   Minerals 15/23 на момент проверки).
2. F8 один раз. Ожидаемо: `PlanetObjectCatalogReady spawn_arrays=10/63/75
   entries=49`; по состоянию save на момент прототипа unknown object entries =
   25 (Flora 17, Mineral 8), fauna unknown = 0.
3. Ожидаемый итог в квесте: Minerals 23/23, Flora 21/21.
4. Если Flora < 21 — сравнить `PlanetObjectCatalogCandidate` с save
   (`analysis/inspect_save_discoveries.py --ua …`); ключи вслепую не отправлять.

### Открытые вопросы

- Правило, по которому 5 flora не входят в знаменатель (26 против 21). Нужно
  для чистоты save, не для полноты счётчика. Направление: Ghidra, код
  страницы Discoveries/квеста, строящий expected list.
- Планета UA `22576276420894979` тоже получила STEAMVENT record; её счётчик не
  проверен.
- Автоскан при ходьбе (идея пользователя: F8 включает режим, подгружающиеся
  рядом объекты сканируются через штатный resolver малыми порциями) —
  отдельная задача после подтверждения F8 v2.
- Ветка, dirty tree, stale `dist/…v1.0.0.zip`: см. «Состояние релиза/Git»
  ниже — всё ещё актуально, ничего не закоммичено.

## Архив: состояние Codex на 2026-09-15 04:xx MSK (устарело)

Релиз **не готов**: на третьей тестовой планете интерфейс Discoveries показывает
`Minerals 17/18`, хотя F8 больше ничего не ставит в очередь. Две предыдущие
планеты действительно закрылись полностью. Текущий дефект локализован намного
точнее, чем старое предположение об Alt-Tab.

- Текущая planet UA: `4561877911412995`.
- Активный сейв: `%APPDATA%\HelloGames\NMS\st_<SteamID>\save7.hg`.
- NMS сейчас запущен через pyMHF, PID на момент handoff `10124`; **не делать
  deploy и не заменять plugin, пока пользователь штатно не закроет игру**.
- Последний runtime log: `logs/pymhf-20260915T041142.log`.
- Пользователь случайно ещё раз нажал F8 при `17/18`; это безопасно: known-check
  дал пустую очередь, новых submit не было.

### Что доказал read-only разбор сейва

Добавлен `analysis/inspect_save_discoveries.py`. Он декодирует chunked LZ4 save
целиком в памяти и ничего не записывает в каталог сохранений. Команда:

```powershell
.\.venv\Scripts\python.exe .\analysis\inspect_save_discoveries.py `
  "$env:APPDATA\HelloGames\NMS\st_<SteamID>\save7.hg" `
  --ua 4561877911412995
```

В save DiscoveryManager для этой UA находятся:

- Animal: 14 records;
- Flora: 32 records;
- Mineral: 18 records, все 18 полных `(key0,key1)` уникальны;
- planet stat `^DISC_MINERALS` также равен `18`;
- UI при этом показывает `17/18`.

Это означает: submit/post-submit добавил хотя бы одну синтетическую запись,
которую настоящий planet discovery catalogue не считает своим минералом.
Следовательно, повторять post-submit для known entries и тем более править save
нельзя — это не лечит источник ошибки.

Сильнейший ложный кандидат:

```text
timestamp 1789433365 (sequence=3 item=10, прямо перед 32.5 s Alt-Tab pause)
keys      106E681A1BFCEDF2:9994F461943ECF7F
resource  MODELS/PLANETS/BIOMES/HQLUSHULTRA/DECORATIVEGRAVELPATCH.SCENE.MBIN
```

Ещё одна такая запись была ошибочно добавлена supplemental-проходом:

```text
timestamp 1789434286
keys      9569667AF122177C:9994F461943ECF7F
resource  .../HQLUSHULTRA/DECORATIVEGRAVELPATCH.SCENE.MBIN
```

У того же seed перед ней была добавлена валиднее выглядящая запись cucumber:

```text
timestamp 1789434284
keys      9569667AF122177C:80C84BC6561043B9
resource  .../UNDERWATER/UPDATEPROPS/CUCUMBERSHAPE.SCENE.MBIN
```

`DECORATIVEGRAVELPATCH.SCENE.MBIN` — container/patch: его scene прямо
прикрепляет `.../COMMON/ROCKS/SMALL/SMALLROCK/ENTITIES/SMALLROCK.ENTITY.MBIN`.
В `TOXICSPORESOBJECTS.MXML` он имеет debug name `DETAILROCKS`, а некоторые
quality variants имеют нулевую density. Статический классификатор ошибочно
решил, что hash container scene и есть discovery key1. Рабочая гипотеза:
настоящий resolver использует leaf scene hash `7E1286D4BCAF9675`
(`.../COMMON/ROCKS/SMALL/SMALLROCK.SCENE.MBIN`), возможно с seed
`106E681A1BFCEDF2`. Это **ещё не доказано**, не submit-ить гипотетический ключ
вслепую.

Alt-Tab первоначально казался причиной из-за паузы сразу после item 10, но save
показывает, что именно item 10 был decorative container. Поэтому focus guard
всё равно полезен для релиза, но не является исправлением `17/18`.

### Новый точный источник object-list данных

В `cGcPlanetData::GenerationData` прочитаны 21 выбранные external object lists
текущей планеты (`analysis/runtime_stage9_external_lists.py`). Среди них:

- `.../TOXIC/TOXICSPORESOBJECTS.MBIN`;
- `.../CAVE/CAVEBIOMEGRASSBUSHES.MBIN`;
- `.../UNDERWATER/UNDERWATERCUCUMBERLIGHTS.MBIN`;
- common plants/crystals/mountain/rare lists.

Все эти MXML уже распакованы под
`%LOCALAPPDATA%\NMSDiscoveryLab\analysis\stage9_all_biomes`.
Добавлен генератор `analysis/build_stage9_object_list_map.py` и сгенерирован
`src/planet_object_lists.py` (251 external lists, 181 nonempty, 1295 scene
memberships). Это пока analysis-only и **не подключено к production F8**.

`analysis/runtime_stage9_external_catalog.py` пересекает выбранные planet lists
с ResourceManager. На текущем процессе он дал 101 entry / 85 seeds / 50 known,
но 51 unknown в основном относятся к старым кластерам других планет системы.
Последний refcount=1 cluster `76172..76286` содержит три неизвестных минерала
`SMALLROCK`, `MEDIUMBOULDER02`, `MEDIUMROCK`; нельзя отправлять все три — UI
говорит, что настоящий missing ровно один. Само membership в выбранном list
недостаточно: нужно восстановить результат planet RNG/merged SpawnData или
найти функцию, которой frontend строит 18 ожидаемых entries.

`cGcPlanetData::SpawnData` был прочитан правильно через `planet_pointer+0x60`,
но в этом build массивы Objects/DetailObjects/DistantObjects/Landmarks пусты,
а SelectableObjects содержит 77 mostly-global templates. Это не merged object
catalogue. Не повторять ошибочный cast `planet_pointer` прямо к cGcPlanetData:
он уже однажды завершил процесс.

### Рекомендуемый следующий шаг

1. Оставаться read-only и найти настоящий merged object list либо frontend
   expected-discovery list. Лучшие направления:
   - Ghidra: функции, которые загружают/merge `cGcExternalObjectList` в runtime
     environment data;
   - Ghidra: xrefs строки/stat id `DISC_MINERALS` и код страницы Discoveries,
     которая получает denominator 18;
   - поймать resolver на реальном экземпляре `DECORATIVEGRAVELPATCH`/leaf rock
     и сравнить key1, если пользователь когда-нибудь встретит последний объект.
2. После доказательства сформировать ровно один unknown `cGcDiscoveryData` и
   сделать отдельный runtime test; пользователь смотрит переход `17/18 -> 18/18`.
3. Затем заменить heuristic `_select_current_planet_object_entries` на точный
   список и исключить container scenes. Добавить тест на decorative container.
4. Добавить foreground/stable-focus guard между paced submit, чтобы Alt-Tab не
   создавал дополнительные риски.
5. Только после новой планеты с полными counters обновить docs, пересобрать zip,
   commit/tag и готовить Nexus/GitHub.

Ghidra проект уже готов:

```text
project dir: %LOCALAPPDATA%\NMSDiscoveryLab\analysis
project:     NMS178938
program:     NMS.exe
headless:    %LOCALAPPDATA%\NMSDiscoveryLab\tools\ghidra_12.1.3_PUBLIC\support\analyzeHeadless.bat
```

Сигнатура `cGcSolarSystemGenerator::GeneratePlanetBiomes` найдена по NMS.py:
file offset `0x163B000`, RVA `0x163BC00`, VA `0x14163BC00`. Отчёт лежит в
`%LOCALAPPDATA%\NMSDiscoveryLab\logs\planet-biomes.txt`; эта функция выбирает
биомные индексы, но сама по себе ещё не показала merged object arrays.

### Состояние релиза/Git

- Ветка: `experiment/stage9-planet-object-catalog`.
- Рабочее дерево намеренно dirty: production code, tests, public docs/launchers
  и analysis scripts не закоммичены.
- `dist/Planetary-Discovery-Scanner-v1.0.0.zip` был собран до обнаружения бага и
  теперь stale; не публиковать.
- README/Nexus description сейчас местами переобещают полный результат; править
  после окончательного алгоритма.
- Git remote отсутствует, GitHub CLI не установлен, ничего на GitHub не
  опубликовано.
- Не удалять пользовательские изменения и не делать reset/checkout.

## Цель и среда

- No Man's Sky Steam, `NMS.exe` file version `178938`, save version `4223`.
- Проект хранится рядом с установленной игрой No Man's Sky.
- Проект: `NMSDiscoveryLab`, Python 3.13 x64, локальная `.venv`, pyMHF и
  `nmspy==178994.0`.
- Работать только offline/single-player. Сохранение имеет отдельную резервную
  копию; пользователь явно разрешил mutation-тесты.
- Не патчить `NMS.exe`, не редактировать save JSON и не добавлять сеть.

Перед изменениями прочитать полностью `README.md`, `docs/findings.md`,
`docs/stage8-test-protocol.md`, `src/discovery_probe.py` и `git log --oneline`.

> Обновление 1.0: этап 9 завершён и подтверждён. Актуальная ветка —
> `experiment/stage9-planet-object-catalog`; описание этапа 8 ниже сохранено как
> исторический контекст, а текущий итог находится в конце этого файла.

## Подтверждённый результат

Ветка `experiment/stage7-player-wide-submit` содержит подтверждённый loaded-area
scanner. F8 без визора получает живые scene nodes в радиусе 1000 м от игрока,
вызывает штатный resolver, оставляет Animal/Flora/Mineral, дедуплицирует по
UA/type/первым трём keys, пропускает известные открытия и отправляет неизвестные
по одному в секунду.

Счётчики игры подтвердили результат:

- stage 6.1: `Flora +2`, `Mineral +1`, точно как `accepted_type_counts` в логе;
- stage 6.2: четыре прохода в одном процессе приняли `3 + 3 + 1 + 1` discovery.

Экранные карточки не появляются, но звук есть и счётчики меняются. Не считать
один `result=True` доказательством: milestone подтверждён именно интерфейсом.

## Build-specific адреса 178994 (Steam build 25320008)

Steam обновил игру 2026-09-15 14:28 до `NMS.exe` 178994. Сдвинулись только код
и глобальные указатели (все globals ровно на `-0xF40`); layouts структур не
изменились — это подтверждает `nmspy==178994.0` (`cGcPlanet` `0xD9170`,
`maPlanets` `+0x2E30`, `Data` `0x94F0E0`, `mSimulation + mpSolarSystem =
0x71AF60`), а `PopulateDiscoveryInfo` 178994 по-прежнему использует
`+0x57A150`, `+0x2CE840`, `+0x307848`.

| что | 178938 | 178994 | как найдено |
|---|---|---|---|
| application-data pointer | `0x6E81828` | `0x6E808E8` | `mov rcx,[rip]` в IsDiscoveryKnown |
| scene-node data pointer | `0x6E13DC8` | `0x6E12E88` | `mov rbx,[rip]` в GetNodeAbsoluteTransform |
| resolver | `0x448DC0` | `0x4490B0` | signature |
| submit | `0x44EB60` | `0x44EE50` | signature |
| is-known | `0x12334B0` | `0x1233C30` | signature |
| post-submit | `0x511560` | `0x511D10` | signature |
| time64 | `0x2BEFC70` | `0x2BEEA70` | signature |

Без изменений: application-data -> solar system `+0x71AF60`; planet
count/inline planets `+0x2544` / `+0x2E30`; stride `0xD9170`; planet-data
CreatureRoles/CreatureSpawns `+0x3180` / `+0x32D8`; spawn arrays
`planet+0x3C08/+0x3C18/+0x3C28`.

С v1.1.0 эти RVA в коде не хранятся (см. раздел v1.1.0 выше); таблица —
справка для ручного анализа. Hard-coded остаются только offsets структур
(`cGcApplication::Data`, `cGcSolarSystem`, `cGcPlanet`); если крупный патч их
изменит, сверять с `nmspy` нового build и `populate-report`-подобными
декомпиляциями, как описано выше.

## Текущий эксперимент

Ветка `experiment/stage8-planet-fauna-catalog` строит полную Animal discovery
очередь непосредственно из `cGcPlanetData::GenerationData.CreatureRoles` и
`SpawnData.Creatures`. Живой scene node животного больше не требуется.

Четыре Animal keys восстановлены полностью:

```text
key0 = role.Seed
key1 = djb2_64(uppercase normalised Resource.Filename)
key2 = mix64(mix64(CreatureID.qword0, CreatureID.qword1), Seed)
key3 = mix64(mix64(planetUA, CreatureType), Info.Rarity)
```

`mix64` использует константу `0x9DDFEA08EB382D69`, shift 47 и unsigned 64-bit
переполнение; точный псевдокод находится в `docs/findings.md`. Все четыре ключа
совпали бит-в-бит с resolver для шести живых видов. Седьмая уже сохранённая
запись BIRD была найдена штатным lookup по первым трём ключам, а её key3 точно
совпал с формулой через `Info.Rarity`.

Этап 8 добавляет полный каталог фауны к прежней paced-очереди. Текущая планета
определяется сопоставлением UA с inline `cGcSolarSystem::maPlanets`; поэтому в
космосе каталог намеренно пропускается. Первый runtime-тест должен проверить,
что `PlanetFaunaCatalogReady.entries` равен общему счётчику животных, а после
очереди счётчик становится полным. Flora/Mineral пока остаются loaded-area.

Не смешивать с экспериментом HUD-уведомлений. Декомпиляция показывает, что
`PopulateDiscoveryInfo` после post-submit отдельно меняет переданный
`DiscoveryInfo` и создаёт HUD-сущность. У массового пути нет безопасного
`DiscoveryInfo` для каждого объекта. Сначала завершить player-centred scanner;
уведомления исследовать отдельной веткой.

## Проверки и запуск

```powershell
Set-Location -LiteralPath "C:\path\to\No Man's Sky\NMSDiscoveryLab"
$env:PYTEST_VERSION='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:PYTEST_VERSION
.\scripts\deploy.ps1
.\scripts\run.ps1 -BackupConfirmed -PreflightOnly
.\scripts\run.ps1 -BackupConfirmed
```

Deploy разрешён только после штатного закрытия `NMS.exe`. Логи находятся в
`NMSDiscoveryLab\logs`. Ошибка Steam 83 иногда возникает как transient launch
race: короткий лог заканчивается после `Serving on executor`; следующий запуск
ранее успешно продолжался без изменения файлов.

## Итог этапа 9 / релиз 1.0

F8 теперь строит полный каталог всех трёх типов без визора и живых scene nodes.
Fauna берётся из planet creature data. Flora/Mineral извлекаются из активного
кластера `cTkResourceManager::mResources`; тип определяется сгенерированным
`src/planet_object_types.py`, `key0` равен descriptor seed, `key1` — DJB2-64
uppercase scene path. Старый синхронный обход 524 288 handles из F8 удалён.

Runtime-подтверждение:

- 26 total / 23 unknown, все 23 приняты (`Animal:6, Flora:6, Mineral:11`),
  каталог 0.551 с;
- 56 total / 56 unknown, все 56 приняты (`Animal:14, Flora:24, Mineral:18`),
  каталог 0.742 с.

Пользователь подтвердил полные счётчики на обеих планетах. Большие HUD-карточки
не реализовывать без отдельного исследования: post-submit и reward path уже
вызываются, но карточка зависит от живого `DiscoveryInfo`/scene entity, которой
для удалённых entries нет. Рабочую реализацию перед релизом не упрощать без
нового runtime-теста.
