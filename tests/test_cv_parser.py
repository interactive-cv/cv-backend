from app.services.cv_parser import parse_master_cv


def test_parse_contacts():
    md = """# Иванов Иван

## Контакты

- **Email**: ivan@example.com
- **Telegram**: @ivan
- **Город**: Москва
- **Формат работы**: удалёнка
- **GitHub**: github.com/ivan
"""
    out = parse_master_cv(md)
    assert out["contacts"]["email"] == "ivan@example.com"
    assert out["contacts"]["telegram"] == "ivan"
    assert out["contacts"]["city"] == "Москва"
    assert out["contacts"]["format"] == "удалёнка"
    assert out["contacts"]["github"] == "github.com/ivan"


def test_parse_summary():
    md = """# Иванов Иван

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
- **Локация**: Москва
- **Формат**: только удалёнка, без релокации
"""
    out = parse_master_cv(md)
    assert out["format"]["city"] == "Москва"
    assert "удалёнка" in out["format"]["format"]
