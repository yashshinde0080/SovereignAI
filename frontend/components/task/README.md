# Task modules — parked on purpose

Only `ChatModule` is wired into the console. These six are deliberately **not**
rendered anywhere: no engine executes their tasks end-to-end yet, so shipping
their UIs would advertise features that don't work.

Parked: `ClassificationModule`, `QAModule`, `MaskedLMModule`, `VisionModule`,
`AudioModule`, `EmbeddingModule`.

They have zero importers on purpose — an "unused component" sweep should not
delete them. `lib/maskedLm.test.ts` already covers the MaskedLM logic, so that
one has real work behind it.

To revive one: wire the engine path first, then render it in
`app/console/page.tsx` and drop that module from the NOTE block there.
