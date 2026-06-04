## Summary


## Change Type

- [ ] Bug fix
- [ ] Documentation
- [ ] Test / CI
- [ ] Packaging
- [ ] Feature

## Impact Area


## Safety Checklist

- [ ] Does not commit `data/`
- [ ] Does not commit `.env`
- [ ] Does not commit `assets/private/`
- [ ] Does not commit `models/`
- [ ] Does not depend on `characters/test_dummy/`
- [ ] Preserves local fallback
- [ ] Preserves transparent pet window, dragging, right-click menu, input box, bubbles, and typewriter

## Verification

- [ ] `pytest -q`
- [ ] `python tools/check_sensitive_files.py`
- [ ] `python tools/check_character_packs.py`
- [ ] `python tools/check_config_templates.py`
- [ ] Documentation updated
