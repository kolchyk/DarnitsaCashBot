# Инструкция по установке зависимостей

## Установка с CPU-only PyTorch (рекомендуется)

Для чтения QR-кодов из чеков достаточно CPU версии PyTorch. Это избежит установки больших библиотек NVIDIA CUDA (~3+ GB).

### Вариант 1: Использовать скрипт установки (Windows)
```bash
install-cpu.bat
```

### Вариант 2: Использовать скрипт установки (Linux/Mac)
```bash
chmod +x install-cpu.sh
./install-cpu.sh
```

### Вариант 3: Установка вручную
```bash
pip install -r requirements-cpu.txt --extra-index-url https://download.pytorch.org/whl/cpu
```

## Установка с CUDA (если нужен GPU)

Если у вас есть NVIDIA GPU и вы хотите использовать его для ускорения:
```bash
pip install -r requirements.txt
```

**Примечание:** Для чтения QR-кодов из чеков GPU не требуется, CPU версии достаточно.

## Проверка установки

После установки можно проверить версию PyTorch:
```python
import torch
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")  # Должно быть False для CPU версии
```

