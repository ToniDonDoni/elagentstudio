# Acceptance Criteria and Test Boundary Guide

## Purpose

This guide explains how to translate user requirements into acceptance criteria, architecture/test-design requirements, implementation tasks, and automated tests.

The goal is to prevent this failure mode:

```text
User requirement: the user must see/hear/click something.
Bad implementation evidence: a class, method, import, label, mock, or requirement ID exists.
```

A requirement is not test-ready until it is expressed as observable behavior at the highest practical test boundary.

## Core chain

Every requirement should be translated through this chain:

```text
User requirement
→ Acceptance criterion
→ Test boundary
→ Architecture / test design requirement
→ Task
→ Automated test
→ Review evidence
```

The reviewer must be able to follow this chain from the original requirement to the actual test assertion.

## Core rule

Every acceptance criterion must answer:

1. What is the initial user/system state?
2. What action happens?
3. What observable result proves success?
4. What is the highest practical automated test boundary?
5. What evidence is explicitly not sufficient?

Do not accept implementation-only criteria such as:

- class exists;
- method exists;
- file exists;
- component is imported;
- object contains a label;
- internal flag changes in isolation;
- requirement ID appears in a test name;
- grep finds the requirement ID;
- coverage table says the requirement is covered.

Those are traceability hints or implementation details. They are not acceptance evidence.

---

## UI user journey rule

For UI work, do not translate requirements directly into isolated controls,
methods, flags, or pixel samples. First write at least one plain user journey:

```text
A person opens the app.
They see ...
They choose ...
They do ...
The app responds by ...
They can tell it worked because ...
```

Then derive acceptance criteria and tests from that journey. If a user journey
contains a visible control, the tests must prove both visibility and operation.
If it contains an input mode, the tests must prove that the selected input mode
actually drives the intended user-observable behavior.

## Example 1: Canvas onboarding journey

### User story

> A person opens the HyperDelusion app for the first time. They see a visible
> onboarding screen with the app title, short instructions, and three visible
> entry-mode choices: Camera, Mouse, and Touch. They choose Mouse. The app enters
> the active experience and the scene responds to mouse movement.

### Correct reasoning chain

1. This is not merely a mode-selection state-machine requirement.
2. The user must be able to see what choices exist before selecting one.
3. It is not enough that hidden coordinate bands change `appState.inputMode`.
4. It is not enough that an `OnboardingScreen` class or `MouseTracker` class
   exists.
5. Acceptance must prove the journey from first page load through visible mode
   selection to user-observable mouse-driven scene response.
6. The test boundary should be browser/rendered-app end-to-end because the
   requirement is about what a person sees and does in the app.

### Acceptance criteria

```text
AC-ONBOARDING-MOUSE-1:
- Given: the app is opened in a browser with no mode selected.
- When: the first screen is displayed.
- Then: the user can visibly identify the app/onboarding screen and the Camera,
  Mouse, and Touch choices.
- Boundary: rendered-app or browser end-to-end.
- Not enough: `OnboardingScreen` exists, `getModeButtons()` returns labels,
  hidden click zones exist, `inputMode` can be changed by clicking undocumented
  coordinates, or a requirement ID appears in a test name.

AC-ONBOARDING-MOUSE-2:
- Given: the visible onboarding choices are displayed.
- When: the user activates the visible Mouse choice.
- Then: the app enters Mouse mode and the active scene is visible.
- Boundary: rendered-app or browser end-to-end.
- Not enough: directly setting `appState.inputMode = "mouse"`, clicking a hidden
  coordinate without proving a visible choice is present, or asserting an
  internal phase flag only.

AC-ONBOARDING-MOUSE-3:
- Given: the app is active in Mouse mode.
- When: the user moves the mouse/pointer across the app.
- Then: the rendered scene changes in the expected perspective/tracking direction
  or exposes an equivalent user-observable response proving Mouse mode drives the
  experience.
- Boundary: browser end-to-end or rendered-app test with real pointer events.
- Not enough: `MouseTracker.handlePointerMove()` exists, a unit test calls the
  tracker directly, or the scene renders static pixels while internal state is
  asserted elsewhere.
```

### Architecture / test design requirement

> The app must render onboarding choices in the actual user-visible surface used
> by the product. The test must open the app, observe visible onboarding choices,
> activate the Mouse choice through the visible UI, dispatch real pointer
> movement events, and assert a rendered or otherwise user-observable scene
> response.

### Task shape

> Add a browser/rendered-app test for the onboarding-to-Mouse journey. The test
> opens the app, proves the Camera/Mouse/Touch choices are visible, clicks the
> visible Mouse choice, moves the pointer, and asserts that the active scene
> changes in a way a user can observe.

### Good test evidence

> The test opens the running app, checks that Camera/Mouse/Touch are visible in
> the rendered screen, clicks the visible Mouse choice, sends pointer movement,
> and compares rendered scene samples or another user-observable signal showing
> that the perspective/tracking changed.

### Bad test evidence

- `OnboardingScreen.render()` exists.
- A method returns `Camera`, `Mouse`, and `Touch` labels.
- The app changes `inputMode` when a test clicks undocumented coordinates.
- `MouseTracker` exists but no app-level pointer event reaches it.
- A unit test calls `MouseTracker.handlePointerMove()` directly.
- A screenshot/pixel sample proves that some pixels changed but not that visible
  mode choices exist or Mouse mode drives the scene.

---

## Example 2: Canvas fallback controls journey

### User story

> A person is using the HyperDelusion app in an active mode. They see fallback
> controls on the canvas: Next question, Sound, and Exit. They click Next
> question and the displayed question changes. They click Sound and the sound
> state visibly or audibly changes. They click Exit and return to the onboarding
> screen.

### Correct reasoning chain

1. This is a user-operable control requirement, not a drawing requirement.
2. The controls must be visible and must work when activated through the real app
   surface.
3. It is not enough that text or rectangles are drawn on the canvas.
4. It is not enough that keyboard shortcut `N` advances the question if the
   requirement names a visible Next control.
5. It is not enough that an internal mute flag changes without the user using the
   visible Sound control.
6. The test boundary should be browser/rendered-app end-to-end because the user
   sees and clicks controls in the rendered app.

### Acceptance criteria

```text
AC-FALLBACK-CONTROLS-1:
- Given: the app is active after a mode has been selected.
- When: the active screen is rendered.
- Then: the user can visibly identify Next question, Sound, and Exit controls.
- Boundary: rendered-app or browser end-to-end.
- Not enough: `getButtonLabels()` returns labels, `postDraw()` contains
  `fillText()`, or non-background pixels exist in a broad region without proving
  which visible control is available.

AC-FALLBACK-CONTROLS-2:
- Given: the visible Next question control is displayed.
- When: the user activates that visible control with a pointer/click/tap.
- Then: the displayed question changes through the app flow.
- Boundary: browser end-to-end or rendered-app test using real pointer events.
- Not enough: pressing keyboard shortcut `N`, directly dispatching an internal
  `NEXT_QUESTION` action, or only proving that the label was drawn.

AC-FALLBACK-CONTROLS-3:
- Given: the visible Sound control is displayed.
- When: the user activates that visible control.
- Then: the app changes sound enabled/muted state and reflects the result through
  the UI or browser/application audio path.
- Boundary: browser end-to-end or rendered-app test with browser-level audio
  instrumentation when audio output is part of the requirement.
- Not enough: an `AudioManager` method exists, a mute boolean changes in an
  isolated unit test, or the word `Sound` appears on the canvas.

AC-FALLBACK-CONTROLS-4:
- Given: the visible Exit control is displayed.
- When: the user activates that visible control.
- Then: the app leaves the active experience and returns to the visible
  onboarding screen.
- Boundary: browser end-to-end or rendered-app test using real pointer events.
- Not enough: directly calling `appState.exit()` or asserting only that an Exit
  label exists.
```

### Architecture / test design requirement

> Canvas-rendered controls must have a corresponding hit-test/input path. The
> test must prove that the same visible control region the user sees can also be
> activated by pointer/click/tap events and that activation produces the required
> user-observable result.

### Task shape

> Add browser/rendered-app tests for the active fallback controls. The tests
> enter an active mode, prove Next/Sound/Exit are visible, click each visible
> control region, and assert the corresponding user-observable result: question
> changes, sound state/output changes, and onboarding returns.

### Good test evidence

> The test enters Mouse or Touch mode, locates or samples the visible control
> regions, clicks the visible Next control and observes the question change,
> clicks the visible Sound control and observes UI/audio state change, and clicks
> Exit and observes the visible onboarding screen again.

### Bad test evidence

- Non-background pixels exist where controls might be.
- `fillText("Next question")` appears in source.
- Keyboard shortcut `N` advances the question, but the visible Next control is
  never clicked.
- `AudioManager.toggleMute()` is tested directly without using the visible Sound
  control.
- Exit is tested but Next and Sound are only visually sampled.

---

## Example 3: Visible UI control

### User requirement

> The app must have a visible “Enable sound” button.

### Correct reasoning chain

1. This is a user-visible UI requirement.
2. Therefore, acceptance must be defined from the user/browser point of view.
3. It is not enough that a class, label, config entry, or component exists.
4. The acceptance criterion must prove that the user can actually see the control.
5. The test boundary should be a rendered-app or browser end-to-end test.

### Acceptance criterion

> Given the app is opened in the browser, then the user can see a visible “Enable sound” button on screen.

### Architecture / test design requirement

> The test must inspect the rendered application as a browser user would see it. A browser automation tool such as Playwright may be used.

### Task shape

> Add an automated browser/rendered-app test that opens the app and asserts that the “Enable sound” button is visible.

### Good test evidence

> The test opens the app in a browser/rendered environment and asserts that the “Enable sound” button is visible to the user.

### Bad test evidence

- A class named `SoundButton` exists.
- A method returns the string `"Enable sound"`.
- `src/main.js` imports a sound component.
- A requirement ID appears in a test name.

---

## Example 4: Browser audio behavior

### User requirement

> The app must play sound.

### Correct reasoning chain

1. This is audible application behavior, not an internal method call.
2. Therefore, acceptance must prove that audio reaches the browser/application audio output path after the real user flow triggers it.
3. It is not enough that an `AudioManager` class has a `play()` method, that a flag says `audioEnabled`, or that an oscillator/node object was constructed in isolation.
4. The test must prove that the app/browser audio path is invoked from the rendered/running application after the required user action.
5. The test boundary should be a browser/rendered-app test with an observable or instrumented audio output signal.
6. The test does not need to physically listen through speakers, but it must observe the browser/application audio output boundary, not only a module boundary.

### Acceptance criterion

> Given the app is opened in the browser and the user performs the required enabling gesture, when the sound-triggering event occurs, then audio is sent to the browser/application audio output path through the real app flow.

### Architecture / test design requirement

> The test must be able to observe audio at the browser/application boundary. This may be done by browser automation with Web Audio instrumentation, a mocked/stubbed `AudioContext` installed in the browser page before the app runs, an analyser/sink node, or another test harness that proves the rendered/running app submitted audio to the browser/application audio output path from the user flow.

### Task shape

> Add an automated browser/rendered-app test that performs the user action required to enable sound, triggers the sound-producing event through the app UI/flow, and verifies that audio reached or was submitted to the browser/application audio output path.

### Good test evidence

> The test opens/renders the app, installs browser-level audio instrumentation before app startup, performs the required user gesture, triggers the sound event through the UI/app flow, and verifies that audio was submitted to the browser/application audio output path, for example by observing `AudioContext` creation/resume plus oscillator/buffer/source connection to a destination or test sink.

### Bad test evidence

- `AudioManager.playSound()` exists.
- A unit test calls `playSound()` directly.
- A boolean `audioEnabled` changes in isolation.
- A file imports `AudioManager`.
- A mocked `AudioContext` is used only inside an isolated module test, without opening/rendering the app or driving the user flow.
- A test asserts that a sound label or configuration exists but does not observe the browser/application audio output path.

---

## Example 5: Backend log output

### User requirement

> The backend must write an audit log entry when an operation completes.

### Correct reasoning chain

1. This is an observable backend side effect.
2. Therefore, acceptance must prove that the application really writes the log entry, not only that a logger method was called.
3. It is not enough that logging code exists, a logger mock was invoked, or a log message string appears in source.
4. The acceptance criterion must prove that the full application path writes the expected log record to the configured destination.
5. The test boundary should be an integration or end-to-end backend test with a real temporary log destination.

### Acceptance criterion

> Given the backend is running with a configured log destination, when the relevant operation is performed through the application boundary, then the expected log entry is written to the actual log destination with the required fields.

### Architecture / test design requirement

> The application must allow the test to configure a temporary log destination. The test must perform the operation through the real application path and then read the log file or event sink produced by the running application.

### Task shape

> Add an automated backend integration test that starts/configures the application with a temporary log path, performs the operation, reads the produced log file, and asserts that the expected log entry exists.

### Good test evidence

> The test configures a temporary log file, performs the real backend operation, reads the log file created by the application, and asserts fields such as `event`, `request_id`, `timestamp`, `status`, and operation-specific data.

### Bad test evidence

- `logger.info()` was called on a mock.
- A log message string exists in source code.
- A logging helper class exists.
- A unit test directly calls the logging helper without running the application path.

---

## Example 6: Backend public API behavior

### User requirement

> The backend public API must accept and return requests/responses according to the specification.

### Correct reasoning chain

1. This is public API behavior visible to API clients.
2. Therefore, acceptance must be defined from the API client's point of view.
3. It is not enough that a service method, controller method, route definition, or DTO exists.
4. The acceptance criterion must prove that the running application accepts the expected request and returns the expected response through the public API boundary.
5. The test boundary should be an API/integration test against the application running in its normal mode or a production-like test mode.

### Acceptance criterion

> Given the backend application is running, when a client sends the specified request to the public API endpoint, then the API returns the expected status, headers, and response body according to the specification.

### Architecture / test design requirement

> The test must be able to start or connect to the application through its public API boundary and send real HTTP/RPC/API requests as a client would. Internal service calls are not enough.

### Task shape

> Add an automated API/integration test that starts the application, sends the specified request to the public API endpoint, and asserts the response status, headers, body, and any required persistent side effect.

### Good test evidence

> The test sends a request to the running application's public API, asserts the returned status/body/schema, and verifies required persistence or emitted side effects when the specification requires them.

### Bad test evidence

- A controller method exists.
- A route is registered.
- A DTO/schema object exists.
- A service method returns the expected object when called directly.
- A unit test bypasses the public API boundary without justification.

---

## Example 7: Backend downstream call

### User requirement

> A request to the application must trigger a call to a downstream system.

### Correct reasoning chain

1. This is an observable integration side effect.
2. Therefore, acceptance must prove that the downstream call happens as a result of the real application request.
3. It is not enough that a client class exists or that a unit test calls the downstream client directly.
4. The acceptance criterion must prove that after the application receives the triggering request, the downstream system or test double receives the expected call.
5. The test boundary should be an integration/end-to-end backend test with a fake downstream server, mock transport, or observable message sink.

### Acceptance criterion

> Given the application is running and a downstream test double is available, when a client sends the triggering request to the application, then the downstream test double receives the expected request/message with the expected payload.

### Architecture / test design requirement

> The application must allow the downstream endpoint/transport to be configured for tests. The test must start the application, start or configure a fake downstream system, send the triggering request to the application, and observe the expected downstream call in the fake system.

### Task shape

> Add an automated backend integration test that starts the application with a fake downstream endpoint, sends the triggering request to the application, and asserts that the fake downstream received the expected request/message.

### Good test evidence

> The test runs the application, runs or configures a fake downstream receiver, sends the public triggering request to the application, and asserts that the fake downstream captured the expected method/path/headers/body or message payload.

### Bad test evidence

- `DownstreamClient.send()` exists.
- A unit test calls `DownstreamClient.send()` directly.
- A mock verifies a method call without sending the triggering request through the application.
- Configuration contains a downstream URL but no test proves the application calls it.

---

## Requirement type → required acceptance shape

### 1. Visual UI requirement

Example requirement:

> The app has a Next question button.

Required acceptance criteria:

- Given the app is opened and active mode is selected,
- then the user can see a “Next question” control on screen.
- When the user activates the control,
- then the displayed question changes.

Required test boundary:

- End-to-end or rendered-app test.
- Browser/rendered DOM must be inspected.
- A class/unit test is not enough unless a higher boundary is genuinely impractical and justified.

Bad test:

> `OnScreenControls.getButtons()` contains `"Next question"`.

Good test:

> Open/render app, select Mouse mode, assert visible “Next question” button, click it, assert visible question changed.

---

### 2. Audio requirement

Example requirement:

> The app plays a sound cue when the question resolves.

Required acceptance criteria:

- Given the app has received a user gesture,
- when the question resolves,
- then audio is sent to the browser/application audio output path through the real app flow.
- Sound must not start before a user gesture.
- The user can mute/unmute sound if a toggle is required.
- If Web Audio is mocked or instrumented, the mock/instrumentation must be installed at the browser/application boundary and exercised by the rendered/running app, not by directly calling the audio module.

Required test boundary:

- Browser/rendered-app boundary test with mocked/stubbed/instrumented Web Audio or another observable browser audio output signal.
- It does not need to hear real sound through speakers, but it must prove the running/rendered app submits audio to the browser/application audio output path from the real user flow.
- A module-level `AudioManager` test is not enough for audible application behavior when a browser/rendered-app boundary is practical.

Bad test:

> `AudioManager.playChime()` exists, or a unit test calls `playChime()` directly.

Good test:

> Open/render app, install browser-level audio instrumentation before startup, perform user gesture, trigger question resolution through app flow, assert that the app created/resumed `AudioContext` and connected or started a source toward a destination/test sink, and assert no audio context was created before user gesture.

---

### 3. Performance requirement

Example requirement:

> The app maintains at least 30 FPS.

Required acceptance criteria:

- Given the production or production-like build is running,
- when the app runs for the target scenario for N seconds,
- then measured FPS is greater than or equal to the threshold.

Required test boundary:

- E2E/performance test against production or production-like build.
- Must record actual timing, memory, FPS, latency, or relevant metrics.

Bad test:

> `RenderProfile` has value `"high"`, or `FrameCostMonitor` class exists.

Good test:

> Launch production build, run the scenario for 10 seconds, collect frame samples, assert FPS / p95 latency / memory threshold.

---

### 4. Backend API requirement

Example requirement:

> `POST /orders` creates an order.

Required acceptance criteria:

- Given a valid request payload,
- when the client sends `POST /orders`,
- then the API returns the expected status and response body,
- and the persisted or emitted side effect is verified.

Required test boundary:

- API/integration test.
- Use the real handler stack where practical.
- Mock only external dependencies.

Bad test:

> `OrderService.create()` returns an object.

Good test:

> Send an HTTP request to the app/server, assert response status/body, and assert a DB row was created or repository mock received the expected write.

---

### 5. Logging / audit requirement

Example requirement:

> The system writes an audit log entry.

Required acceptance criteria:

- Given the relevant action occurs,
- when the action completes,
- then a log entry is written to the expected destination,
- and the log entry contains the required fields.

Required test boundary:

- Integration test using a temporary log destination.
- Verify actual file/event-sink content.

Bad test:

> `logger.info()` was called in a unit mock.

Good test:

> Configure a temporary log path, perform the real action, read the log file, and assert a JSON line exists with `event`, `request_id`, `timestamp`, and `status`.

---

### 6. External integration requirement

Example requirement:

> The app sends a notification to service X.

Required acceptance criteria:

- Given the triggering condition occurs,
- when the system processes it,
- then an outbound request/message is sent with the expected payload.

Required test boundary:

- Integration test with fake server, mock transport, or contract test.
- The workflow should be triggered through the real application path where practical.

Bad test:

> `NotificationClient.send()` exists.

Good test:

> Trigger the real workflow and assert the fake external service received the expected request/payload.

---

## Acceptance criteria generation rules

For every requirement, generate acceptance criteria in this form:

```text
AC-<REQ>-<N>:
- Given: initial user/system state
- When: user/system action
- Then: observable result
- Boundary: unit / integration / rendered-app / end-to-end / performance
- Not enough: implementation-only evidence that must not satisfy this AC
```

If the requirement mentions any of these words or ideas:

- visible;
- button;
- screen;
- user can;
- click;
- tap;
- keyboard;
- sound;
- audio;
- animation;
- browser;
- performance;
- FPS;
- memory;
- latency;
- API response;
- file/log output;
- external call;

then the acceptance criterion must include an application-boundary, rendered-app, browser, integration, or performance test unless explicitly justified.

---

## Reviewer rule

A reviewer must not mark a requirement covered unless the test proves the acceptance criterion at the declared boundary.

For each covered requirement, the reviewer must identify:

- exact acceptance criterion;
- exact test file;
- exact user/system action in the test;
- exact assertion proving the observable result;
- why the chosen boundary is the highest practical stable boundary.

If the reviewer can only point to a class, method, import, label, mock state, file existence, or requirement ID string, coverage is missing.

---

## Anti-patterns

### Bad: implementation disguised as acceptance

```text
Requirement: The user can enable sound.
Bad AC: Implement AudioManager.toggleMute().
```

Why it is bad:

> The user cannot see or use `AudioManager.toggleMute()` directly. This does not prove the user can enable sound in the app.

Correct AC:

```text
Given the app is active,
then the user can see a sound toggle.
When the user activates the sound toggle,
then the app changes sound enabled/muted state through the app audio path and reflects the state in UI.
Boundary: rendered-app or browser end-to-end test with audio instrumentation.
```

### Bad: import treated as wiring proof

```text
Requirement: The active app screen has an Exit button.
Bad evidence: src/main.js imports OnScreenControls.
```

Why it is bad:

> Importing a component does not prove the user can see or activate the control.

Correct evidence:

```text
The test opens/renders the app, enters active mode, asserts the Exit button is visible, clicks it, and observes that onboarding is visible again.
```

### Bad: requirement ID treated as coverage

```text
Requirement: FR-020 fallback controls.
Bad evidence: A test file contains the string "FR-020".
```

Why it is bad:

> Requirement IDs provide traceability only. They do not prove behavior.

Correct evidence:

```text
The test performs the fallback control action and asserts the observable result required by FR-020.
```

---

## Final rule

If the requirement is about something the user sees, hears, clicks, taps, types, waits for, receives, stores, logs, sends, or experiences, then acceptance criteria must be written from that observable boundary.

Do not turn user requirements into class existence, method existence, imports, labels, mocks, or grep hits.

Good acceptance criteria are boring and concrete:

```text
Given state.
When action.
Then observable result.
Boundary: highest practical automated test boundary.
Not enough: implementation-only evidence.
```
