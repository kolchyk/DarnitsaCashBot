# Настройка Cloudflare R2 для DarnitsaCashBot

Пошаговая инструкция по созданию аккаунта Cloudflare R2 и настройке хранилища для проекта.

## Шаг 1: Создание аккаунта Cloudflare

1. Перейдите на [cloudflare.com](https://www.cloudflare.com/)
2. Нажмите **"Sign Up"** (Зарегистрироваться)
3. Заполните форму регистрации:
   - Email адрес
   - Пароль
   - Подтвердите email

## Шаг 2: Активация R2

1. После входа в аккаунт Cloudflare, перейдите в **Dashboard**
2. В левом меню выберите **R2** (или перейдите по прямой ссылке: [dash.cloudflare.com/r2](https://dash.cloudflare.com/r2))
3. Если R2 еще не активирован, нажмите **"Enable R2"** или **"Get started"**
4. Примите условия использования и активируйте R2

## Шаг 3: Создание Bucket

1. В разделе R2 нажмите **"Create bucket"**
2. Заполните форму:
   - **Bucket name**: `darnitsa-receipts` (или другое имя на ваш выбор)
   - **Location**: Выберите ближайший регион:
     - `EEUR` - Eastern Europe (Восточная Европа) - **рекомендуется для Украины**
     - `WNAM` - Western North America (Западная Северная Америка)
     - `ENAM` - Eastern North America (Восточная Северная Америка)
     - `APAC` - Asia Pacific (Азиатско-Тихоокеанский регион)
3. Нажмите **"Create bucket"**

**Примечание:** Регион bucket влияет на физическое расположение данных и может влиять на задержку. Для проекта в Украине рекомендуется выбрать `EEUR` (Eastern Europe).

## Шаг 4: Создание API токенов (R2 Token)

1. В разделе R2 перейдите в **"Manage R2 API Tokens"** (или нажмите на иконку профиля → **"My Profile"** → **"API Tokens"**)
2. Нажмите **"Create API token"**
3. Выберите шаблон **"Edit Cloudflare R2"** или создайте кастомный:
   - **Permissions**: 
     - Object Read & Write
     - Account Read
   - **Account Resources**: 
     - Include: All accounts (или выберите конкретный аккаунт)
   - **Zone Resources**: Не требуется для R2
4. Нажмите **"Continue to summary"** → **"Create Token"**
5. **ВАЖНО**: Скопируйте и сохраните:
   - **Access Key ID**
   - **Secret Access Key** (показывается только один раз!)

## Шаг 5: Получение Account ID

1. В Dashboard Cloudflare выберите ваш аккаунт
2. В правой панели найдите **"Account ID"** (или перейдите в **"My Profile"** → **"API Tokens"** → там будет указан Account ID)
3. Скопируйте Account ID (формат: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`)

## Шаг 6: Определение Endpoint URL

Endpoint URL для Cloudflare R2 имеет формат:
```
https://<account-id>.r2.cloudflarestorage.com
```

Где `<account-id>` - это ваш Account ID из шага 5.

**Пример:**
```
https://a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6.r2.cloudflarestorage.com
```

## Шаг 7: Настройка на Heroku

После получения всех данных выполните команды:

```bash
# Замените значения на ваши реальные данные
heroku config:set STORAGE_ENDPOINT=https://<your-account-id>.r2.cloudflarestorage.com
heroku config:set STORAGE_BUCKET=darnitsa-receipts
heroku config:set STORAGE_ACCESS_KEY=<your-access-key-id>
heroku config:set STORAGE_SECRET_KEY=<your-secret-access-key>
heroku config:set STORAGE_REGION=auto
```

**Пример:**
```bash
heroku config:set STORAGE_ENDPOINT=https://a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6.r2.cloudflarestorage.com
heroku config:set STORAGE_BUCKET=darnitsa-receipts
heroku config:set STORAGE_ACCESS_KEY=your-actual-access-key-id-here
heroku config:set STORAGE_SECRET_KEY=your-actual-secret-access-key-here
heroku config:set STORAGE_REGION=auto
```

## Шаг 8: Проверка конфигурации

Проверьте, что все переменные установлены правильно:

```bash
heroku config | grep STORAGE
```

Должны быть видны все 5 переменных:
- `STORAGE_ENDPOINT`
- `STORAGE_BUCKET`
- `STORAGE_ACCESS_KEY`
- `STORAGE_SECRET_KEY`
- `STORAGE_REGION`

## Шаг 9: Тестирование подключения

Используйте скрипт для проверки подключения (см. `scripts/test_r2_connection.py`):

```bash
heroku run python scripts/test_r2_connection.py
```

Или протестируйте через API:

```bash
# Замените YOUR_TELEGRAM_ID на ваш реальный Telegram ID
curl -X POST https://your-app.herokuapp.com/bot/receipts?telegram_id=YOUR_TELEGRAM_ID \
  -F "file=@test.jpg"
```

## Шаг 10: Настройка Lifecycle Policy (опционально)

Для автоматического удаления файлов старше 90 дней:

1. В Cloudflare Dashboard → R2 → выберите ваш bucket
2. Перейдите в **"Settings"** → **"Lifecycle Rules"**
3. Нажмите **"Create rule"**
4. Настройте:
   - **Rule name**: `delete-old-receipts`
   - **Object prefix**: `receipts/` (или оставьте пустым для всех объектов)
   - **Expire objects after**: `90 days`
5. Сохраните правило

## Полезные ссылки

- [Cloudflare R2 Dashboard](https://dash.cloudflare.com/r2)
- [R2 Documentation](https://developers.cloudflare.com/r2/)
- [R2 API Tokens](https://dash.cloudflare.com/profile/api-tokens)
- [R2 Pricing](https://developers.cloudflare.com/r2/pricing/)
- [R2 S3 API Compatibility](https://developers.cloudflare.com/r2/api/s3/api/)

## Безопасность

⚠️ **Важные рекомендации:**

1. **Никогда не коммитьте** Access Key ID и Secret Access Key в Git
2. Храните ключи только в Heroku Config Vars
3. Используйте минимально необходимые права доступа для API токена
4. Регулярно ротируйте ключи доступа (каждые 90 дней)
5. Включите двухфакторную аутентификацию в Cloudflare аккаунте

## Troubleshooting

### Ошибка: "Access Denied"
- Проверьте, что Access Key ID и Secret Access Key правильные
- Убедитесь, что API токен имеет права на R2
- Проверьте, что bucket name указан правильно

### Ошибка: "Bucket not found"
- Убедитесь, что bucket создан и имя указано правильно
- Проверьте регион bucket'а

### Ошибка: "Invalid endpoint"
- Проверьте формат endpoint URL: `https://<account-id>.r2.cloudflarestorage.com`
- Убедитесь, что Account ID правильный (32 символа)

### Ошибка подключения
- Проверьте, что endpoint URL доступен (можно проверить через curl)
- Убедитесь, что нет проблем с сетью Heroku

## Мониторинг использования

В Cloudflare Dashboard → R2 вы можете отслеживать:
- Использованное хранилище (GB)
- Количество операций (чтение/запись)
- Трафик (входящий/исходящий)

Бесплатный план включает:
- 10 GB хранилища
- 1,000,000 операций в месяц

После превышения лимитов начнется плата по тарифам.

