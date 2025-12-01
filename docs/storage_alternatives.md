# Альтернативные варианты S3-совместимого хранилища

Этот документ описывает различные варианты S3-совместимого хранилища для проекта DarnitsaCashBot, которые можно использовать вместо локального MinIO в продакшене.

## Рекомендуемые варианты

### 1. **Cloudflare R2** ⭐ (Рекомендуется)

**Преимущества:**
- ✅ Бесплатный egress (нет платы за исходящий трафик)
- ✅ Низкая стоимость хранения ($0.015/GB/месяц)
- ✅ Полная совместимость с S3 API
- ✅ Быстрая глобальная сеть CDN
- ✅ Бесплатный план: 10GB хранения, 1M операций в месяц

**Настройка на Heroku:**

```bash
# Создайте bucket в Cloudflare Dashboard (R2)
# Получите Access Key ID и Secret Access Key

heroku config:set STORAGE_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
heroku config:set STORAGE_BUCKET=your-bucket-name
heroku config:set STORAGE_ACCESS_KEY=your-r2-access-key-id
heroku config:set STORAGE_SECRET_KEY=your-r2-secret-access-key
heroku config:set STORAGE_REGION=auto  # или us-east-1
```

**Ссылки:**
- [Cloudflare R2 Documentation](https://developers.cloudflare.com/r2/)
- [R2 Pricing](https://developers.cloudflare.com/r2/pricing/)

---

### 2. **Backblaze B2**

**Преимущества:**
- ✅ Очень низкая стоимость ($0.005/GB/месяц)
- ✅ Первые 10GB бесплатно
- ✅ S3-совместимый API
- ✅ Надежное хранилище (11 9's durability)
- ✅ Бесплатный egress до определенного лимита

**Настройка на Heroku:**

```bash
# Создайте bucket в Backblaze B2
# Создайте Application Key с правами на bucket

heroku config:set STORAGE_ENDPOINT=https://s3.us-west-004.backblazeb2.com
heroku config:set STORAGE_BUCKET=your-bucket-name
heroku config:set STORAGE_ACCESS_KEY=your-b2-key-id
heroku config:set STORAGE_SECRET_KEY=your-b2-application-key
heroku config:set STORAGE_REGION=us-west-004  # или ваш регион
```

**Ссылки:**
- [Backblaze B2 S3 Compatible API](https://www.backblaze.com/b2/docs/s3_compatible_api.html)
- [B2 Pricing](https://www.backblaze.com/b2/cloud-storage-pricing.html)

---

### 3. **DigitalOcean Spaces**

**Преимущества:**
- ✅ Простая настройка
- ✅ Предсказуемая цена ($5/месяц за 250GB + $0.02/GB)
- ✅ S3-совместимый API
- ✅ CDN включен бесплатно
- ✅ Хорошая интеграция с Heroku

**Настройка на Heroku:**

```bash
# Создайте Space в DigitalOcean
# Получите Access Key и Secret Key

heroku config:set STORAGE_ENDPOINT=https://<region>.digitaloceanspaces.com
heroku config:set STORAGE_BUCKET=your-space-name
heroku config:set STORAGE_ACCESS_KEY=your-do-access-key
heroku config:set STORAGE_SECRET_KEY=your-do-secret-key
heroku config:set STORAGE_REGION=nyc3  # или ams3, sgp1, sfo3, etc.
```

**Ссылки:**
- [DigitalOcean Spaces Documentation](https://docs.digitalocean.com/products/spaces/)
- [Spaces Pricing](https://www.digitalocean.com/pricing/spaces-object-storage)

---

### 4. **AWS S3** (Стандартный вариант)

**Преимущества:**
- ✅ Надежность и масштабируемость
- ✅ Широкий выбор регионов
- ✅ Интеграция с другими AWS сервисами
- ✅ Подробная документация

**Недостатки:**
- ❌ Высокая стоимость egress трафика
- ❌ Сложная структура цен

**Настройка на Heroku:**

```bash
# Создайте S3 bucket в AWS Console
# Создайте IAM user с правами на bucket

# Для AWS S3 endpoint можно не указывать (None) или использовать региональный endpoint
heroku config:unset STORAGE_ENDPOINT  # или не устанавливайте
heroku config:set STORAGE_BUCKET=your-bucket-name
heroku config:set STORAGE_ACCESS_KEY=your-aws-access-key-id
heroku config:set STORAGE_SECRET_KEY=your-aws-secret-access-key
heroku config:set STORAGE_REGION=us-east-1  # или ваш регион
```

**Ссылки:**
- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [AWS S3 Pricing](https://aws.amazon.com/s3/pricing/)

---

### 5. **Scaleway Object Storage**

**Преимущества:**
- ✅ Европейский провайдер (GDPR compliance)
- ✅ Низкая стоимость ($0.01/GB/месяц)
- ✅ S3-совместимый API
- ✅ Бесплатный egress до 75GB/месяц

**Настройка на Heroku:**

```bash
# Создайте bucket в Scaleway Console
# Создайте API ключ

heroku config:set STORAGE_ENDPOINT=https://s3.<region>.scw.cloud
heroku config:set STORAGE_BUCKET=your-bucket-name
heroku config:set STORAGE_ACCESS_KEY=your-scaleway-access-key
heroku config:set STORAGE_SECRET_KEY=your-scaleway-secret-key
heroku config:set STORAGE_REGION=fr-par  # или nl-ams, pl-waw
```

**Ссылки:**
- [Scaleway Object Storage](https://www.scaleway.com/en/object-storage/)
- [Scaleway S3 Compatibility](https://www.scaleway.com/en/docs/storage/object/api-cli/s3-compatibility/)

---

### 6. **Wasabi**

**Преимущества:**
- ✅ Очень низкая стоимость ($0.0059/GB/месяц)
- ✅ Нет платы за egress
- ✅ S3-совместимый API
- ✅ Быстрая производительность

**Настройка на Heroku:**

```bash
# Создайте bucket в Wasabi Console
# Создайте Access Key

heroku config:set STORAGE_ENDPOINT=https://s3.<region>.wasabisys.com
heroku config:set STORAGE_BUCKET=your-bucket-name
heroku config:set STORAGE_ACCESS_KEY=your-wasabi-access-key
heroku config:set STORAGE_SECRET_KEY=your-wasabi-secret-key
heroku config:set STORAGE_REGION=us-east-1  # или us-east-2, us-west-1, eu-central-1
```

**Ссылки:**
- [Wasabi Cloud Storage](https://wasabi.com/)
- [Wasabi S3 API Compatibility](https://wasabi.com/api-docs/)

---

### 7. **Stackhero MinIO** (Управляемый MinIO для Heroku)

**Преимущества:**
- ✅ Прямая интеграция с Heroku как addon
- ✅ Знакомый MinIO интерфейс
- ✅ Простая настройка через Heroku CLI

**Настройка на Heroku:**

```bash
# Установите Stackhero MinIO addon
heroku addons:create stackhero-minio:free

# Переменные окружения устанавливаются автоматически
# Проверьте их:
heroku config | grep STORAGE
```

**Ссылки:**
- [Stackhero MinIO Addon](https://elements.heroku.com/addons/stackhero-minio)
- [Stackhero Documentation](https://www.stackhero.io/en/documentations/MinIO/)

---

## Сравнительная таблица

| Провайдер | Стоимость хранения | Egress трафик | Бесплатный план | Рекомендация |
|-----------|-------------------|---------------|-----------------|--------------|
| **Cloudflare R2** | $0.015/GB | Бесплатно | 10GB | ⭐⭐⭐⭐⭐ Лучший выбор |
| **Backblaze B2** | $0.005/GB | Бесплатно до лимита | 10GB | ⭐⭐⭐⭐ Отличный вариант |
| **DigitalOcean Spaces** | $5/250GB | Включен | Нет | ⭐⭐⭐⭐ Хорошо для старта |
| **AWS S3** | $0.023/GB | Дорого | Нет | ⭐⭐⭐ Стандарт индустрии |
| **Scaleway** | $0.01/GB | 75GB/мес бесплатно | Нет | ⭐⭐⭐⭐ Для EU |
| **Wasabi** | $0.0059/GB | Бесплатно | Нет | ⭐⭐⭐⭐ Дешево |
| **Stackhero MinIO** | Зависит от плана | Зависит от плана | Free tier | ⭐⭐⭐ Для Heroku |

## Рекомендации по выбору

### Для стартапа / MVP:
1. **Cloudflare R2** - лучший баланс цены и функциональности
2. **Backblaze B2** - самый дешевый вариант
3. **DigitalOcean Spaces** - если уже используете DO

### Для продакшена с большим трафиком:
1. **Cloudflare R2** - нет платы за egress
2. **Wasabi** - предсказуемые цены без egress fees

### Для европейских проектов (GDPR):
1. **Scaleway** - европейский провайдер
2. **DigitalOcean Spaces** (EU регионы)

### Для максимальной надежности:
1. **AWS S3** - проверенное решение
2. **Cloudflare R2** - современная инфраструктура

## Миграция с MinIO

Все перечисленные провайдеры используют S3-совместимый API, поэтому миграция проста:

1. Создайте bucket у нового провайдера
2. Установите переменные окружения на Heroku (см. инструкции выше)
3. При необходимости мигрируйте существующие файлы (можно использовать `aws s3 sync` или `rclone`)
4. Протестируйте загрузку нового файла
5. Обновите документацию

## Проверка конфигурации

После настройки проверьте подключение:

```bash
# Проверьте переменные окружения
heroku config | grep STORAGE

# Протестируйте загрузку через API
curl -X POST https://your-app.herokuapp.com/bot/receipts?telegram_id=YOUR_TELEGRAM_ID \
  -F "file=@test.jpg"

# Проверьте логи на наличие ошибок
heroku logs --tail | grep -i storage
```

## Безопасность

Для всех провайдеров рекомендуется:

1. ✅ Использовать минимально необходимые права доступа
2. ✅ Регулярно ротировать ключи доступа
3. ✅ Включить версионирование объектов (если поддерживается)
4. ✅ Настроить lifecycle policies для автоматического удаления старых файлов (90 дней согласно требованиям)
5. ✅ Использовать HTTPS для всех endpoint'ов
6. ✅ Включить логирование доступа к bucket'у

## Lifecycle Policy (пример для AWS S3)

Для автоматического удаления файлов старше 90 дней можно настроить lifecycle policy:

```json
{
  "Rules": [
    {
      "Id": "DeleteOldReceipts",
      "Status": "Enabled",
      "Expiration": {
        "Days": 90
      }
    }
  ]
}
```

Аналогичные настройки доступны у большинства провайдеров через их веб-интерфейс или API.

