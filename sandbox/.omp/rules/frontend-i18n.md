---
description: Frontend i18n — namespaces, locale parity, no hardcoded user-visible text
globs:
      - frontend/src/locales/**/*.ts
      - frontend/src/sections/**/*.tsx
      - frontend/src/pages/*.tsx
      - frontend/src/layouts/**/*.tsx
alwaysApply: false
---

# Frontend I18n

A missing translation key does not fail a build and does not throw: i18next
renders the key itself, so `user.table.username` ships to a user. Every check
here exists because the runtime is silent.

Machine-checked by `check-frontend-i18n.ts` (`make check-frontend-i18n`).

## Layout

| File | Contains |
|---|---|
| `locales/ko.ts` | Korean — the default *and* the fallback language |
| `locales/en.ts` | English — the same key set, field for field |
| `locales/i18n.ts` | init: `defaultNS: 'common'`, `fallbackLng: 'ko'`, and `SUPPORTED_LANGUAGES` |

**`SUPPORTED_LANGUAGES` in `i18n.ts` is the list of languages** — the checker
reads it rather than carrying its own. The two must agree in both directions: a
`locales/<x>.ts` absent from it is never loaded and never checked for parity
(measured: a third language file passed every check), and a name in it with no
file fails at startup.

Namespaces: `common` (words every screen needs), `nav`, `auth`, and one per
domain. Korean is the fallback because this is a Korean-first product — falling
back to English would show a user text they cannot read, and falling back to the
key shows them nothing at all.

**A placeholder is a contract, and both halves are checked.** `{{user}}가 {{at}}에
수정` called with `{ actor, at }` renders the literal `{{user}}` on the screen —
i18next leaves an unmatched placeholder in the output, and every other check stays
green because the key exists and is translated in both locales. That shipped once,
caught by eye. `check-frontend-i18n` now compares the names a `t(key, { … })` call
passes against the `{{names}}` the string declares, in either direction: a renamed
value, a dropped one, and a renamed placeholder in the locale all fire.

## Using a Namespace

```tsx
const { t } = useTranslation('user')       // t('table.username')
const { t: tCommon } = useTranslation('common')
const { t: tNav } = useTranslation('nav')
```

`useTranslation()` with no argument resolves against `common` — so
`t('nav.dashboard')` under a bare `useTranslation()` looks up
`common.nav.dashboard` and renders the key. Name the namespace.

A dynamic key (`t(item.titleKey)`) cannot be verified, so the key it builds must
be a bare key inside a named namespace: `useTranslation('nav')` +
`titleKey: 'dashboard'`, never a dotted path against the default namespace.

## Server Failures Are Codes, Not Sentences

The backend answers every failure with `{ detail, code, request_id }`. `detail`
is English written for a log; the user reads a translation keyed by `code`:

```ts
// locales/ko.ts and locales/en.ts, same keys
errors: {
  conflict: '이미 사용 중인 값입니다',
  provider_code_invalid: '코드는 영소문자·숫자·하이픈만 사용합니다',
  unknown: '요청을 처리할 수 없습니다',
}
```

- The UI renders `t('errors.<code>', { ns: 'common' })` — **never**
  `apiError.message`, never `detail`. Rendering the server's string ships
  English into a Korean screen and hard-codes copy the frontend cannot change.
- Every code the backend can emit has a key in **every** locale. A new failure
  mode without a translation is a gate failure, not an `unknown_error` on screen.
- `errors.unknown` is the fallback for a transport failure that never reached a
  handler, so it always exists.
- A dialog may put the message on the input that owns it (`conflict` →
  the `code` field), but the sentence still comes from the locale file.

## What Is Checked

1. **Locale parity, both ways** — a key in `ko` and not in `en` is a silent
   fallback only an English user sees
2. **Every literal `t('key')` resolves** in the namespace its alias was bound to
3. **No Korean outside `locales/`** — text that bypassed i18n cannot be
   translated at all, and it is the one violation that is invisible in review
   when the reviewer reads Korean
4. **Error-code parity, both ways** — every `code` the backend can emit
   (handler literals in `app/core/exceptions.py` plus `code=` at any raise site)
   has `errors.<code>` in every locale, and an `errors.*` key no backend code
   emits is dead copy
5. **No server string on screen** — `apiError.message`, `error.message` and
   `detail` never reach a toast or JSX; the sentence comes from the locale file

## Review Judgement (not machine-checked)

- Whether a translation is *correct*. Key parity is checked; a wrong Korean
  sentence with a matching key passes.
- Whether a dynamic key (`t(item.titleKey)`) resolves. Only literal keys can be
  verified, so a computed key is a review concern — keep it a bare key inside a
  named namespace so the possible values are visible in one file.
- Korean inside a **comment** is exempt: a comment quoting the string it
  explains is how the reason survives, and flagging it would push authors to
  write vaguer comments.

## Never Do These

- Add a key to one language and not the other
- Use a dotted path against the default namespace (`t('nav.logout')`)
- Put user-visible Korean in a component, a comment excepted only in `locales/`
- Interpolate a name into a sentence by concatenation — use `{{name}}`
- Read a label from a hook when the screen already has `t`
- Render a server `detail` (or `ApiError.message`) as user-facing copy
- Add a backend error code without an `errors.<code>` entry in every locale
- Reuse one code for two failures a user must tell apart
