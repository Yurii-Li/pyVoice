# 🚀 Інструкція: Як випустити нову версію PyVoice AI (Inno Setup)

У проєкті налаштовано систему випуску офіційних Windows-інсталяторів через **Inno Setup** з автоматичним тихою оновленням клієнтських додатків.

---

## 🛠️ Як це працює для користувачів та друзів:

1. **Перше встановлення:**
   * Користувач завантажує `PyVoiceAI-Setup.exe` з [GitHub Releases](https://github.com/Yurii-Li/pyVoice/releases).
   * Інсталятор встановлює програму у папку користувача (`%LocalAppData%\Programs\PyVoice AI`) **без потреби прав адміністратора** (не запитує UAC пароль!).
   * Створюються акуратні ярлики на Робочому столі та в меню Пуск.

2. **Автоматичне оновлення:**
   * При виході нової версії додаток сам пропонує оновитися (або по кнопці `🔄 v...` у статус-барі).
   * Програма скачує свіжий `PyVoiceAI-Setup.exe` і запускає його в тихому режимі (`/SILENT /CLOSEAPPLICATIONS`).
   * Inno Setup сам акуратно закриває старий додаток, оновлює файли та ярлики, і одразу запускає нову версію!

---

## 📦 Як випустити нову версію (GitHub Actions — Автоматично)

Все робиться всього 4 командами через git:

### 1. Підніміть версію в коді:
У файлі `src/pyvoice/__init__.py`:
```python
__version__ = "1.5.0"  # вкажіть вашу версію
```
Також переконайтеся, що версія співпадає в `installer.iss`:
```iss
#define MyAppVersion "1.5.0"
```

### 2. Закомітьте зміни та створіть тег:
```cmd
git add .
git commit -m "release: v1.5.0 - switch to Inno Setup installer and auto-updater"
git tag v1.5.0
git push origin main
git push origin v1.5.0
```

### 3. Що зробить GitHub Actions:
* Сервер GitHub сам встановить Python, збере `PyVoiceAI.exe` через PyInstaller.
* Встановить Inno Setup і скомпілює офіційний інсталятор `PyVoiceAI-Setup.exe`.
* Опублікує реліз на сторінці **https://github.com/Yurii-Li/pyVoice/releases** з обома файлами:
  1. `PyVoiceAI-Setup.exe` (Офіційний інсталятор із підтримкою автооновлень)
  2. `PyVoiceAI.exe` (Портативна версія)
