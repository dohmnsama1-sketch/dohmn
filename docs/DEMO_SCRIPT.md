# MendCart demonstration script

Target: **2 minutes 35 seconds**. Record the actual application running in a browser. This storyboard is a recording plan, not evidence that the sandbox walkthrough has happened.

## Recording gate

Run the app with the local model, verify a blocked budget, then complete an actual sandbox order, buyer approval and capture. Confirm displayed status comes from the provider. Keep secrets, dashboard credentials and personal payer details out of the recording.

If recording before credentials exist, label it a **local preview** and replace it before claiming a complete sandbox demonstration. Use original graphics and no third-party music. Final upload must be public on YouTube and shorter than three minutes.

## Storyboard

| Time | Browser action | Narration |
|---|---|---|
| 0:00–0:18 | Show the workshop request. | “When workshop equipment fails, buying a replacement is easy. Deciding whether a repair is enough takes more care. MendCart helps a buyer prepare that decision within an authorized budget.” |
| 0:18–0:35 | Show synthetic data disclosure and model mode. | “This prototype uses synthetic catalog records. Its local machine learning model learns from original maintenance examples. AI identifies the request; procurement policy controls the cart.” |
| 0:35–1:00 | Build a leaking pump plan with a $120 cap; show items and total. | “Our workshop's pump is leaking. We want a repair before a replacement, with a ceiling of one hundred and twenty dollars. MendCart explains its selection using the supported demo catalog.” |
| 1:00–1:18 | Build again with $10; show blocked checkout. | “With ten dollars authorized, this plan cannot proceed. The server checks the budget. AI output does not override it.” |
| 1:18–1:40 | Restore $120, build a fresh plan and authorize it. | “The buyer reviews a specific plan and authorizes it. MendCart stores that plan in the session, so checkout uses the same items and amount.” |
| 1:40–2:12 | Create actual sandbox order; open approval, approve, return and capture. | “PayPal creates a sandbox order. The buyer approves in PayPal. On return, MendCart verifies provider state and captures the authorized sandbox purchase.” |
| 2:12–2:35 | Show completed sandbox status and events. | “The result is a traceable path from repair intent to an authorized cart and sandbox receipt. Next come real compatibility data and evaluation with workshop buyers.” |

## Editing notes

- Keep the final video below 2:50 to leave a margin.
- If cutting login pauses, preserve order continuity. Never splice a fixture response into the provider sequence.
- Sandbox purchase and capture are not revenue.
- Local mode is a narrow classifier, not an external LLM.
- Avoid measured savings, verified compatibility or real inventory claims.
- Add English captions if narration is in another language.
