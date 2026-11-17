# Model Provider Feasibility — 2026-11-15

**Decision:** No model provider is selected or wired into the factory yet.

## Verified market constraints

| Option | Current public documentation | Decision |
|---|---|---|
| GitHub Models | The service was fully retired on July 30, 2026, including its inference API and BYOK | Not available; do not design around it |
| Gemini Developer API free tier | Free access is limited to selected models; Google's pricing page states that free-tier content may be used to improve its products | Not approved for private source code or confidential task content |
| Hugging Face Inference Providers | Free users receive $0.10 monthly inference credit, subject to change; additional usage is pay-as-you-go | Useful only for tiny experiments, not a dependable agent runtime |
| OpenAI API | API billing is separate from ChatGPT subscription billing | Requires a separately verified API credit grant or explicit budget |
| Groq API | Free plan has model-specific organization-level request/token limits; exact limits are account-specific | Candidate for a public-code experiment only after account, privacy, and rate-limit review |

## Source links

- GitHub Models retirement: https://github.blog/changelog/2026-07-30-github-models-is-now-retired/
- Gemini API pricing and free-tier data use: https://ai.google.dev/gemini-api/docs/pricing
- Hugging Face inference pricing: https://huggingface.co/docs/inference-providers/pricing
- OpenAI ChatGPT/API billing separation: https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform
- Groq rate limits: https://console.groq.com/docs/rate-limits

## Current architecture decision

1. Keep the provider adapter interface separate from task validation and orchestration.
2. For the first supervised prototype, ChatGPT remains the human-facing planning/implementation assistant; GitHub Actions performs deterministic validation and CI. This is not unattended agent execution.
3. Do not send private code to a free-tier provider whose terms permit use of submitted content for product improvement.
4. Do not assume a ChatGPT subscription provides an API key, API credits, or unlimited external automation.
5. Do not enable automatic paid usage. Any metered API requires an explicit spend ceiling and approval.
6. Revisit local inference only after verifying an OS, CPU/RAM, and GPU combination that can run a supported coding model at usable speed.

## What remains unresolved

- A privacy-acceptable model endpoint and its data-retention/training terms.
- Exact rate limits and reliability for the selected account.
- Cost per task and hard spending cap.
- Independent reviewer model/provider, distinct from the implementer.
- Secret delivery from a runtime without exposing credentials to GitHub logs or task artifacts.

Until those are verified, the factory must fail closed before any model-dependent action.
