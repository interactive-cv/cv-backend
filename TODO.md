# Дорожная карта / TODO

## Универсализация: сделать шаблон полностью параметрическим ✅

Цель достигнута: чужое CV разворачивается **только** заменой контента (`seed_data/`) и `.env`, без правки исходников.

- [x] `app/routers/admin.py` — URL короткой ссылки через `SITE_URL` из `.env`
- [x] `app/llm/prompts.py` — имя кандидата парсится из первой строки `master_cv.md` (`# Имя`)
- [x] `app/config.py` — `SITE_URL` добавлен, `contacts_fallback` без дефолта
- [x] `docker-compose.prod.yml` — `LE_EMAIL`, `LE_FQDN`, `NEXT_PUBLIC_API_URL` с примерами и комментарием
- [x] `nginx_ssl/conf/service_cv.conf` — `server_name` с примером + комментарий «замените на свой домен»
- [x] `app/layout.tsx`, `opengraph-image.tsx`, `robots.ts`, `sitemap.ts`, `Hero.tsx` — через `lib/site.ts` (env: `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_OWNER_NAME`, `NEXT_PUBLIC_OWNER_ROLE`)
- [x] `seed_data/master_cv.md`, `projects.json` → `.example`, реальный контент каждый создаёт сам; `seed.py` подсказывает скопировать из примера

## Прочее по развитию

- [ ] Админ-панель (UI) для управления вариантами CV и короткими ссылками из браузера
- [ ] Расширенная аналитика просмотров и переходов по коротким ссылкам
- [ ] Поддержка тёмной/светлой темы переключателем
- [ ] Контрибьютинг-гайд (`CONTRIBUTING.md`) и лицензия (MIT) для open-source
