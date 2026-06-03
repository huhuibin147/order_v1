# order_v1

轻量级多人点单 H5。详见 [DESIGN.md](./DESIGN.md)。

## 启动

```bash
pip install -r requirements.txt
python app.py
```

打开 http://localhost:35001 ，手机连同一 WiFi 访问 `http://<电脑IP>:35001` 即可。

## 目录

```
.
├── app.py              # Flask 后端
├── data/menu.json      # 菜单数据
├── templates/          # HTML 模板
├── static/             # CSS / JS
├── DESIGN.md           # 设计文档
└── requirements.txt
```
