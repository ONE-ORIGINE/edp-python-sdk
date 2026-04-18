# EnvLang Reference

EnvLang supports:

- `let x:int = 3`
- `do alice :: action.type key=value`
- `parallel{ ... | ... }`
- `sequence{ ... ; ... }`
- `if <cond> then { ... } else { ... }`
- `call <plan>`
- `remote <peer> { ... }`
- named outputs via `=> name`
- template interpolation via `${var.name}` and `${result.label.path}`
