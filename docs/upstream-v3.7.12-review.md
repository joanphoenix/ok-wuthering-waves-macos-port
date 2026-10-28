# Upstream v3.7.12 update attempt

Reviewed October 28, 2026. **Live navigation and teleport now pass; a full combat clear remains unverified.** See the latest retest section at the end. Automated tests alone do not establish gameplay compatibility. The initial findings and test failures below are retained as history, followed by the migration results.

## Initial update attempt

- Latest non-prerelease release verified through GitHub's releases/latest endpoint: [v3.7.12](https://github.com/ok-oldking/ok-wuthering-waves/releases/tag/v3.7.12).
- Upstream release commit: `46113e464b823c95d5df988f8eba8b2dd8b45e5e`; annotated tag object: `911abbed57740818fe170ec8b2f27942d3b2c376`.
- Starting Mac port commit: `23c4038816e450228ccc335d68b498d3c16f35e6`.
- Branch: `codex/update-upstream-v3.7.12`.
- Applied the binary-capable diff from `v3.7.12-beta.1` to `v3.7.12` using `git apply --3way`; these repositories do not have a common merge base. No patch conflicts occurred.
- Preserved the Mac README and all pre-existing Mac adaptations. No changes have been made to the vendored `ok-script/` framework.
- The imported delta changes 406 files, largely the upstream migration from 51 packed template images to individual crops. It includes Roccia C6 behavior, team export/info UI, pickup filtering, and combat restart handling.
- Changes are staged for review, with this report added separately. Nothing has been committed or pushed. The original `main` branch still points to the starting commit.

## Initial blocker (now resolved): template API and framework mismatch

Upstream now requires `ok-script[ocr,qt]>=2.0.17` and configures `template_matching.template_folder` in `config.py`. Its packed `assets/images/` files have been removed and replaced with `assets/templates/` crops.

However, the Mac launcher sets `PYTHONPATH` to the bundled `ok-script/` directory. That bundled `FeatureSet` constructor does not accept `template_folder`, and `OK.do_init` only reads `coco_feature_json`. Updating or installing a PyPI dependency alone would still leave this bundled code selected by the launcher.

Evidence:

- `config.py:214`: selects `template_folder`.
- `ok-script/ok/feature/FeatureSet.py:71`: constructor lacks the new parameter.
- `ok-script/ok/__init__.py:1039`: reads the now-absent `coco_feature_json` setting and does not forward the template directory.
- Focused template tests raise `TypeError: FeatureSet.__init__() got an unexpected keyword argument 'template_folder'`.
- A harness mirroring the production constructor call and passing a 1280x720 blank frame to `check_size` raises `TypeError: stat: path should be string, bytes, os.PathLike or integer, not NoneType`.

The required next step is to integrate the matching framework/template-loader changes while retaining the Mac capture, input, window geometry, and Qt adaptations. A dry-run of the full framework v2.0.15-to-v2.0.17 patch also found missing files and conflicts, including `FeatureSet.py`, metadata, and resources. The bundled framework does not exactly match the released v2.0.15 tree; it needs a deliberate migration rather than a blanket replacement. That dry-run did not modify files.

## Existing findings still relevant

These were identified in the earlier port review and are not introduced by this upstream update:

- Global Quartz input has no enforced foreground guard; actions can reach another app after focus changes (`ok-script/ok/device/interaction_methods/macos_quartz.py`).
- Cached window scale/title metrics omit display/position, allowing stale scale after moving an unchanged-size window between Retina and non-Retina displays (`ok-script/ok/util/window_macos.py:175`).
- The launcher only installs dependencies if `.venv/bin/python` is absent; an interrupted installation leaves a venv that subsequent launches do not repair (`run_macos.sh:8`).
- The README still names upstream v3.7.7 and overstates OCR acceleration: the installed ONNX OCR path selects CPU; the YOLO path has CoreML provider selection.

## Verification

All commands used the repository's `.venv/bin/python`, `PYTHONPATH=ok-script:.`, and offscreen Qt for pytest. No live gameplay or synthetic input was run.

1. Focused release/port tests: **84 passed, 19 failed (including failed subtests), 19 subtests passed, 1 deselected**. The failures all report the template constructor mismatch.

   ```sh
   PYTHONPATH=ok-script:. QT_QPA_PLATFORM=offscreen ./.venv/bin/python -m pytest -q tests/TestOneTimeCombatRestart.py tests/TestAbyssRestart.py tests/TestAutoPickTask.py tests/TestRocciaCombat.py tests/TestCustomCharLoader.py tests/TestTeamEvaluation.py tests/test_f2_challenge_selection.py tests/test_tacet_elimination.py -k 'not config_widgets_instantiation'
   ```

2. Broader regression tests: **159 passed, 2 failed, 1 skipped, 55 subtests passed**. Both failures are Hsin template tests using the unsupported constructor parameter.

   ```sh
   PYTHONPATH=ok-script:. QT_QPA_PLATFORM=offscreen ./.venv/bin/python -m pytest -q tests/TestCharacterCodeTab.py tests/TestConfig.py tests/TestMouseResetImport.py tests/TestMultiAccountConfig.py tests/test_hsin.py tests/test_rover.py tests/test_suoming.py tests/test_suoming_heavy.py tests/test_phrolova_switch.py
   ```

3. Previously crashing widget test: **1 passed, 8 deselected** when run alone with offscreen Qt. The earlier crash is not confirmed as an application defect.

   ```sh
   PYTHONPATH=ok-script:. QT_QPA_PLATFORM=offscreen ./.venv/bin/python -m pytest -q tests/test_f2_challenge_selection.py -k config_widgets_instantiation
   ```

4. Syntax parsing: all **20 changed Python files** passed.
5. `git diff --cached --check`: passed; no unmerged paths.

Combined test runs: **244 passed; 21 failures including failed subtests; 1 skipped**. These are selected checks, not the full suite. Live capture, input, and end-to-end gameplay remain unverified. Test logs are under `/private/tmp/ok-ww-stable-*-tests.log` and `/private/tmp/ok-ww-stable-widget-test.log` for this session.


## Migration results after owner approval

Backported the v2.0.17 template loader/generator into the bundled framework, forwarded `template_folder` in `OK.do_init`, and integrated the upstream split/compressed template export UI. Imported the upstream template generation tests and export-dialog regression test. The existing legacy compressed-export implementation was retained, as were all Mac capture, input, geometry, and native UI adaptations. This is a compatibility backport, not a blanket upgrade of the entire framework to v2.0.17.

Updated the README's upstream version and corrected its OCR acceleration claim. The pre-existing focus handling, scale-cache, and launcher recovery issues remain outside this migration.

Validation after migration:

- Combined selected release, character, Mac configuration, restart, template generation, and UI regression tests: **272 passed, 2 skipped, 106 subtests passed**. All previously failing template checks now pass. Command: the union of both original test lists above, plus `ok-script/tests/test_template_generation.py`, with offscreen Qt and without the original deselection.
- Template tab tests excluding `markup_close`: **9 passed** (`-k 'not markup_close'`). This includes the new split/compressed export-dialog check.
- Loaded all **296 features and 296 boxes** at 1280x720, 1920x1080, 2560x1440, 3840x2160, and 2560x1080, using the actual application template settings. New Roccia, pickup-filter, and Abyss templates were present at every resolution.
- Remaining validation limitation: `test_markup_close_emits_the_editor_coco_data` crashes in the installed `qframelesswindow.mac.updateFrameless` while converting an offscreen Qt window handle to a Cocoa object. That native-window path cannot be validated with this offscreen test run. No production fix or skip was added to conceal the crash.
- No live game capture/input or full end-to-end gameplay was exercised. Nothing committed or pushed; changes remain on `codex/update-upstream-v3.7.12`.


## Final resolution of the reported Mac issues

- Input now requires foreground game focus and dispatches keyboard, text, scroll, and mouse events to the game PID instead of the global HID tap. Focus loss aborts the current input operation and releases tracked held keys/buttons to the game. The global pynput fallback was removed. Activation remains explicit at task startup to avoid stealing focus back while running.
- Window metrics now check the captured backing image dimensions before reusing cached title-bar measurements. Position, logical dimensions, and physical dimensions participate in the cache key, including display-resolution changes at a fixed window origin.
- The launcher validates Python 3.12 and writes a dependency fingerprint only after a successful install. Incomplete installs retry; changed launcher/dependency settings trigger a refresh. Root package metadata and README now match the documented Python 3.12 support range.
- Spinbox styling and constructor compatibility now share one Mac-only, idempotent compatibility module. Removed the duplicate application-wide stylesheet. Windows widgets do not receive the workaround.
- Offscreen/minimal Qt on macOS uses a QWidget window adapter for BaseWindow instead of passing synthetic handles into Cocoa's native frameless implementation. Real desktop windows retain the native backend. The previously crashing markup test now runs and passes; no skip was added.
- The README's upstream version and CPU OCR wording were corrected during migration.

Final selected verification: **288 passed, 2 skipped, 110 subtests passed** across the migration regression set, full template-tab tests, and new Mac input/scale/installer/compatibility regressions. The test command is the combined migration regression list plus `tests/test_macos_port_regressions.py`, `tests/test_macos_launcher.py`, and the full `ok-script/tests/test_template_tab.py`, with `PYTHONPATH=ok-script:. QT_QPA_PLATFORM=offscreen` and the local virtual environment. Log: `/private/tmp/mac-all-regressions.log`.

Launcher shell syntax and Git whitespace checks pass. No real input was sent during tests. Live capture, gameplay, and game acceptance of process-targeted input remain to be checked on the desktop. Changes remain local, uncommitted, and unpushed on `codex/update-upstream-v3.7.12`.


## Live test, October 28, 2026

- The native Qt app launched successfully with desktop access. The sandbox-only launch could not access screens, which is an execution-environment limitation.
- Switched to the localhost browser interface because the UI automation tool could not bind the native Python window. The same runtime selected `MacOSQuartzCaptureMethod`, initialized CPU OCR, captured a 3024x1898 game frame, and warmed 66 character templates.
- Ran the existing Nightmare Nest task briefly, with unrelated triggers temporarily disabled. It failed before travel/combat: `can't find gray_book_boss, make sure f2 is the hotkey for book`. The executor stopped; no successful combat was demonstrated.
- The port's `bring_window_to_front` attempts timed out twice in its existing System Events/osascript path. Window metrics also passed through transient miniature sizes (including 280x120) and retained those crop dimensions briefly while the window expanded. These are observed live problems requiring further diagnosis.
- Direct UI-tool F2 input opened the game's Activity interface. This proves that direct UI input reaches the game; it does not prove that the port's process-targeted input is accepted. Input delivery versus guidebook-template recognition remains unresolved.
- Restored the trigger preferences changed for testing and left the executor stopped. No purchases, account changes, or stamina-spending tasks were intentionally performed.
- Live runtime log: `/private/tmp/ok-ww-live-web.log`; native startup log: `/private/tmp/ok-ww-live-session.log`. The browser control interface is localhost-only; it remains available for follow-up testing.

The earlier passing test counts establish regression coverage, not live gameplay compatibility. Do not treat the port as release-ready until input/navigation and transient window geometry are resolved and a combat run succeeds.


## Navigation fixes and second live test

Implemented three targeted corrections:

1. `bring_window_to_front` uses native NSRunningApplication activation directly, eliminating the System Events timeout before fallback. The activation regression failed before the fix and passes after it.
2. Quartz capture checks current full backing geometry and discards mismatched transition frames. It crops using current client dimensions, never stale discovery-time `real_width`/`real_height`. A regression reproduced the erroneous 280x120 crop before the fix and now passes.
3. Foreground game actions use the HID event stream, which the game accepted during retesting. Foreground is checked again at dispatch. Cleanup releases after focus loss remain PID-targeted. The earlier blanket PID dispatch was not compatible with live gameplay input. This corrects the earlier descriptions claiming that all dispatch remains process-targeted. A final focus check reduces dispatch races but is not an atomic OS guarantee against focus changing immediately afterward.

Live results (two navigation runs):

- F2 guidebook opening and `gray_book_boss` matching succeeded (logged confidence 86%).
- Selected the combat sidebar, OCR-matched `Tacet Discord Nest`, chose an unfinished nest, and clicked teleport.
- Teleport completed and Hsin, Suoming, and Shorekeeper were identified with roughly 98-99% template confidence.
- Entered the nest encounter. Both attempts were interrupted by the out-of-screen safety pause while the game window moved horizontally. The second attempt was observed through logs without further UI actions during the travel/combat interval. Resuming the first interrupted rotation produced `too long clicking a liberation` and a keybinding warning; this is not evidence of a successful rotation or clear.
- The remaining out-of-screen pause was not suppressed. The cause of that window movement and the interrupted-combat recovery need further diagnosis. A complete combat clear is still unverified.
- The source-run browser updater also logged an unsupported `pyappify_version: None` error; no application upgrade was performed.
- Stopped the Nightmare Nest task and left global automation paused. Trigger preferences were not changed during this retest. The new local interface is at `http://127.0.0.1:63634/` for this session.

Evidence: `/private/tmp/ok-ww-live-retest.log`. Focused corrections initially passed **66 tests, 1 skipped, 8 subtests passed**; final combined regression results are recorded below. Changes remain local, uncommitted and unpushed.

Final combined regressions after these corrections: **291 passed, 2 skipped, 110 subtests passed**. Log: `/private/tmp/ok-ww-final-retest-tests.log`. Git whitespace checks pass.

## Final retry and publication scope

A further fresh-task retry again paused almost immediately when window tracking reported the game partly offscreen at `(839, 33)`. The task was stopped before navigation/combat. The out-of-screen safety check remains enabled; a successful combat clear is still unverified.

The owner subsequently requested merging all prepared changes into the Antigravity checkout and publishing them to `joanphoenix/ok-wuthering-waves-macos-port` main. Earlier references to uncommitted/unpushed work describe the state at those testing checkpoints. This publication includes the documented live-test limitations and is not a claim of release readiness.
