import { Card, Divider, message, Slider, Space, Switch, Typography } from 'antd'
import { BellOutlined, WarningOutlined } from '@ant-design/icons'
import { useSettingsStore } from '../../store/useSettingsStore'

export default function AlertSettings() {
  const workloadThresholdPct = useSettingsStore((s) => s.workloadThresholdPct)
  const browserNotifyEnabled = useSettingsStore((s) => s.browserNotifyEnabled)
  const setWorkloadThreshold = useSettingsStore((s) => s.setWorkloadThreshold)
  const setBrowserNotify = useSettingsStore((s) => s.setBrowserNotify)

  const handleNotifyToggle = async (val: boolean) => {
    if (val) {
      if (!('Notification' in window)) {
        void message.warning('このブラウザはプッシュ通知に対応していません')
        return
      }
      const perm = await Notification.requestPermission()
      if (perm !== 'granted') {
        void message.warning('ブラウザの通知を許可してください（ブラウザ設定を確認してください）')
        return
      }
    }
    setBrowserNotify(val)
    void message.success(val ? 'ブラウザ通知を有効にしました' : 'ブラウザ通知を無効にしました')
  }

  const thresholdColor =
    workloadThresholdPct <= 80 ? '#52c41a' : workloadThresholdPct <= 100 ? '#faad14' : '#ff4d4f'

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <div>
        <Typography.Title level={5} style={{ margin: 0 }}>
          アラート設定
        </Typography.Title>
        <Typography.Text type="secondary">
          ワークロードアラートの閾値とブラウザ通知の設定を管理します。
        </Typography.Text>
      </div>

      <Card
        title={
          <Space>
            <WarningOutlined style={{ color: '#faad14' }} />
            ワークロードアラート閾値
          </Space>
        }
      >
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <Typography.Text>
            キャパシティの何%を超えたらアラートを表示するかを設定します。
          </Typography.Text>
          <div style={{ padding: '0 16px' }}>
            <div style={{ textAlign: 'center', marginBottom: 8 }}>
              <Typography.Title level={3} style={{ margin: 0, color: thresholdColor }}>
                {workloadThresholdPct}%
              </Typography.Title>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                キャパシティの {workloadThresholdPct}% を超えた日をアラート表示
              </Typography.Text>
            </div>
            <Slider
              min={50}
              max={150}
              step={5}
              value={workloadThresholdPct}
              onChange={setWorkloadThreshold}
              marks={{
                50: '50%',
                80: '80%',
                100: '100%',
                120: '120%',
                150: '150%',
              }}
              styles={{
                track: { backgroundColor: thresholdColor },
              }}
            />
          </div>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            例: 80% に設定すると、予定工数がキャパシティの 80%
            を超えた日からアラート表示されます（早期警告）。
          </Typography.Text>
        </Space>
      </Card>

      <Divider />

      <Card
        title={
          <Space>
            <BellOutlined />
            ブラウザ通知
          </Space>
        }
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <div>
              <Typography.Text strong>ワークロード超過通知</Typography.Text>
              <br />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                ワークロードがアラート閾値を超えたときにブラウザ通知を送信します
              </Typography.Text>
            </div>
            <Switch
              checked={browserNotifyEnabled}
              onChange={(v) => void handleNotifyToggle(v)}
              checkedChildren="ON"
              unCheckedChildren="OFF"
            />
          </Space>
          {browserNotifyEnabled && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              ※ ブラウザがフォーカスされていない場合にのみ通知が表示されます
            </Typography.Text>
          )}
        </Space>
      </Card>
    </Space>
  )
}
