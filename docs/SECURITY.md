# Security

## Do Not Commit

Do not commit:

- Firebase Web API keys for production projects.
- Service account JSON.
- Firebase CLI token files.
- FCM device tokens.
- Private resume files.
- Seen job history tied to a real person.
- Production project IDs if the repo will be public.
- Private roadmap or operating logs.

## Firebase Web API Keys

Firebase Web API keys are not server secrets, but production project identifiers and auth surfaces are still operational metadata. For a public template, keep real config in a private profile or deploy repo and commit only examples.

## Identity

FCM device tokens are not identity credentials. Use Firebase Auth or another real auth layer for client writes.

## Runtime Credentials

This repo expects runtime credentials to be provided by the operator's environment, such as Firebase CLI login or another adapter. The public repo should not contain credential values.

## Secret Scanning

Before making this repo public, run:

```bash
rg -n --hidden -g '!\.git' -g '!__pycache__' -g '!*.pyc' -i '(AIza|apiKey|client_secret|private[_-]?key|serviceAccount|refresh_token|password|token)' .
```

