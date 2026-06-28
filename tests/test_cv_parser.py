from app.services.cv_parser import parse_master_cv


def test_parse_contacts():
    md = """# Григорьев Валерий

## Контакты

- **Email**: vrg18@vk.com
- **Telegram**: @vrg18
- **Город**: Геленджик
- **Формат работы**: только удалёнка, без релокации
- **GitHub**: github.com/vrg18
"""
    out = parse_master_cv(md)
    assert out["contacts"]["email"] == "vrg18@vk.com"
    assert out["contacts"]["telegram"] == "vrg18"
    assert out["contacts"]["city"] == "Геленджик"
    assert out["contacts"]["format"] == "только удалёнка, без релокации"
    assert out["contacts"]["github"] == "github.com/vrg18"


def test_parse_summary():
    md = """# Григорьев Валерий

## Summary

Flutter / Fullstack разработчик с 11+ годами опыта.

## Профессиональные навыки
"""
    out = parse_master_cv(md)
    assert "11+ годами" in out["summary"]


def test_parse_skills_table():
    md = """## Навыки и умения (конкретные технологии)

| Категория | Технологии |
|-----------|------------|
| **Языки программирования** | Dart, Java, JavaScript/TypeScript, Python, 1C |
| **Frameworks** | Flutter, Spring, FastAPI |
"""
    out = parse_master_cv(md)
    assert out["skills_core"]["Языки программирования"] == [
        "Dart", "Java", "JavaScript/TypeScript", "Python", "1C"
    ]
    assert out["skills_core"]["Frameworks"] == ["Flutter", "Spring", "FastAPI"]


def test_parse_languages():
    md = """## Языки
- **Русский** — родной
- **Английский** — Intermediate: читаю тех. документацию.
"""
    out = parse_master_cv(md)
    assert out["languages"]["Русский"] == "родной"
    assert "Intermediate" in out["languages"]["Английский"]


def test_parse_format():
    md = """## Формат работы
- **Локация**: Геленджик
- **Формат**: только удалёнка, без релокации
"""
    out = parse_master_cv(md)
    assert out["format"]["city"] == "Геленджик"
    assert "удалёнка" in out["format"]["format"]
