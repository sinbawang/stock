# Kline Cache Cloud Backup Runbook

本手册用于把本地 `data/cache/kline` 缓存目录备份到 CloudBase/COS 目录 `stock-kline-cache/latest`，并支持新实例恢复。

## 目标

- 热缓存仍在本地磁盘，保证分析读写速度。
- 云存储目录做备份和灾备恢复。
- 支持定时备份和停机前备份。

## 前置条件

- 已配置 `CLOUDBASE_ENV_ID`
- 已配置 `CLOUDBASE_REGION`
- 已配置 `CLOUDBASE_APIKEY`
- 已完成 CloudBase CLI 登录（恢复命令默认依赖 `tcb storage download --dir`）

如果不提供 `CLOUDBASE_APIKEY`，脚本会尝试使用 `TENCENT_SECRET_ID/TENCENT_SECRET_KEY` 生成临时 key。

## 一键健康检查

在新实例上建议先执行检查：

```bash
python3 scripts/sync_kline_cache_cloudbase.py check
```

需要机器可读输出时：

```bash
python3 scripts/sync_kline_cache_cloudbase.py check --json
```

如果当前阶段只想跳过登录态阻断（仍保留其他硬性检查）：

```bash
python3 scripts/sync_kline_cache_cloudbase.py check --allow-not-logged-in
```

恢复前建议先验证 CLI 登录态：

```bash
tcb env list --json
```

如果在 Windows PowerShell 被执行策略拦截，请使用：

```powershell
& "C:\\Users\\<your-user>\\AppData\\Local\\Microsoft\\WinGet\\Packages\\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\\node-vxx\\tcb.cmd" login
```

## 一次性手工备份

```bash
python3 scripts/sync_kline_cache_cloudbase.py backup \
  --source-dir data/cache/kline \
  --cloud-prefix stock-kline-cache/latest \
  --manifest-path build/stock-kline-cache/cloudbase-upload-manifest.json
```

首次备份建议加 `--force-upload`，保证所有文件都上传。

## 一次性恢复到本地缓存

```bash
python3 scripts/sync_kline_cache_cloudbase.py restore \
  --target-dir data/cache/kline \
  --cloud-prefix stock-kline-cache/latest \
  --clean-target
```

说明：

1. 默认走 `tcb storage download ... --dir`，整目录恢复，不依赖本地 manifest。
2. 如需只看命令不执行，可加 `--dry-run`。

## Linux 包装脚本

- 备份脚本: `bin/linux/backup_kline_cache_to_cloudbase.sh`
- 恢复脚本: `bin/linux/restore_kline_cache_from_cloudbase.sh`
- 健康检查脚本: `bin/linux/check_kline_cache_cloudbase.sh`
- systemd 一键安装脚本: `bin/linux/install_kline_cache_backup_systemd.sh`

示例：

```bash
bash bin/linux/backup_kline_cache_to_cloudbase.sh --force-upload
bash bin/linux/restore_kline_cache_from_cloudbase.sh --fetch-manifest
```

## systemd 定时备份

模板文件：

- `bin/linux/systemd/stock-kline-cache-backup.service`
- `bin/linux/systemd/stock-kline-cache-backup.timer`

安装步骤（以 `/opt/stock` 为部署目录示例）：

```bash
sudo cp bin/linux/systemd/stock-kline-cache-backup.service /etc/systemd/system/
sudo cp bin/linux/systemd/stock-kline-cache-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stock-kline-cache-backup.timer
sudo systemctl status stock-kline-cache-backup.timer --no-pager
```

也可以使用一键安装脚本：

```bash
sudo bash bin/linux/install_kline_cache_backup_systemd.sh
```

可选覆盖参数：

```bash
sudo SERVICE_USER=ubuntu WORKING_DIR=/opt/stock CLOUD_PREFIX=stock-kline-cache/latest MANIFEST_PATH=/opt/stock/build/stock-kline-cache/cloudbase-upload-manifest.json bash bin/linux/install_kline_cache_backup_systemd.sh
```

## 新实例自动化（cloud-init）

如果你不想在每台新实例手工执行安装，可在创建 CVM 时直接使用 cloud-init。

模板文件：

- `bin/linux/cloud-init/install-kline-cache-backup.yaml`

使用步骤：

1. 把模板中的 `<YOUR_REPO_URL>`、`<YOUR_BRANCH>`、`CLOUDBASE_APIKEY` 替换为真实值。
2. 在腾讯云创建实例时，把该 YAML 作为 user-data 注入。
3. 实例首启后 cloud-init 会自动：
  - 拉取代码到 `/opt/stock`
  - 写入 `/etc/default/stock-kline-cache`
  - 执行 systemd 一键安装脚本
  - 触发一次首轮备份

验证命令：

```bash
systemctl status stock-kline-cache-backup.timer --no-pager
journalctl -u stock-kline-cache-backup.service -n 200 --no-pager
```

注意：

1. 模板里默认把 `CLOUDBASE_APIKEY` 写入 `/etc/default/stock-kline-cache`，权限是 `0600`。
2. 更高安全要求场景建议改为实例启动后从密钥管理服务注入，而不是在模板里明文保存。

说明：

1. `stock-kline-cache-backup.service` 已内置 `ExecStartPre`，会先跑健康检查。
2. 健康检查失败时不会执行上传，错误会写入 journald。

## systemd 停机前备份

模板文件：

- `bin/linux/systemd/stock-kline-cache-shutdown-backup.service`

安装步骤：

```bash
sudo cp bin/linux/systemd/stock-kline-cache-shutdown-backup.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable stock-kline-cache-shutdown-backup.service
sudo systemctl status stock-kline-cache-shutdown-backup.service --no-pager
```

说明：

1. 停机前服务同样带 preflight 检查。
2. 如需排障，先看：

```bash
journalctl -u stock-kline-cache-backup.service -n 200 --no-pager
journalctl -u stock-kline-cache-shutdown-backup.service -n 200 --no-pager
```

## 推荐环境文件

建议新建 `/etc/default/stock-kline-cache`：

```bash
CLOUDBASE_ENV_ID=your-env-id
CLOUDBASE_REGION=ap-shanghai
CLOUDBASE_APIKEY=your-api-key
CLOUD_PREFIX=stock-kline-cache/latest
MANIFEST_PATH=/opt/stock/build/stock-kline-cache/cloudbase-upload-manifest.json
```

## 验证

```bash
python3 scripts/sync_kline_cache_cloudbase.py backup --dry-run
python3 scripts/sync_kline_cache_cloudbase.py restore --dry-run
```

如果恢复后还要保证当次分析继续增量，可直接执行你的既有报告生成命令，程序会在本地缓存基础上继续合并更新。
