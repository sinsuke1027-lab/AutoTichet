import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert, Button, Result, Space, Steps, Table, Typography, Upload,
} from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd'
import api, { type ImportPreviewResponse, type ImportResult } from '../../lib/api'

const { Dragger } = Upload
const { Title, Text } = Typography

export default function ImportPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handlePreview = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post<ImportPreviewResponse>('/import/asana/preview', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setPreview(res.data)
      setStep(1)
    } catch {
      setError('プレビューの取得に失敗しました。xlsx ファイルを確認してください。')
    } finally {
      setLoading(false)
    }
  }

  const handleConfirm = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post<ImportResult>('/import/asana/confirm', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(res.data)
      setStep(2)
    } catch {
      setError('インポートに失敗しました。')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setStep(0); setFile(null); setPreview(null); setResult(null); setError(null)
  }

  const sectionColumns = [
    { title: 'セクション名', dataIndex: 'name', key: 'name' },
    { title: 'タスク数', dataIndex: 'task_count', key: 'task_count' },
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Title level={3}>Asana データインポート</Title>
      <Steps
        current={step}
        items={[
          { title: 'ファイル選択' },
          { title: 'プレビュー確認' },
          { title: '完了' },
        ]}
      />

      {error && <Alert type="error" message={error} closable onClose={() => setError(null)} />}

      {step === 0 && (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Dragger
            accept=".xlsx"
            maxCount={1}
            beforeUpload={(f) => { setFile(f); return false }}
            onRemove={() => setFile(null)}
            fileList={file ? [{ uid: '1', name: file.name, status: 'done' } as UploadFile] : []}
          >
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">.xlsx ファイルをドロップするかクリックして選択</p>
            <p className="ant-upload-hint">Asana からエクスポートした Excel ファイルをアップロードしてください</p>
          </Dragger>
          <Button
            type="primary"
            disabled={!file}
            loading={loading}
            onClick={handlePreview}
          >
            プレビューを取得
          </Button>
        </Space>
      )}

      {step === 1 && preview && (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Title level={4}>インポート内容の確認</Title>
          <Space direction="vertical">
            <Text>プロジェクト: <strong>{preview.projects[0]?.name}</strong>（新規作成）</Text>
            <Text>タスク合計: <strong>{preview.tasks.total}</strong> 件（完了済み: {preview.tasks.completed} 件）</Text>
            <Text>サブタスク: {preview.tasks.with_subtasks} 件</Text>
          </Space>

          <Table
            rowKey="name"
            dataSource={preview.sections}
            columns={sectionColumns}
            size="small"
            pagination={false}
            title={() => <Text strong>セクション一覧</Text>}
          />

          {preview.warnings.length > 0 && (
            <Alert
              type="warning"
              message="警告"
              description={
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  {preview.warnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              }
            />
          )}

          <Space>
            <Button onClick={handleReset}>キャンセル</Button>
            <Button type="primary" loading={loading} onClick={handleConfirm}>
              インポート実行
            </Button>
          </Space>
        </Space>
      )}

      {step === 2 && result && (
        <Result
          status="success"
          title="インポート完了"
          subTitle={`タスク ${result.created_tasks} 件・セクション ${result.created_sections} 件 を作成しました（重複スキップ: ${result.skipped_duplicates} 件）`}
          extra={[
            <Button key="projects" type="primary" onClick={() => navigate('/projects')}>
              プロジェクトを見る
            </Button>,
            <Button key="again" onClick={handleReset}>
              別のファイルをインポート
            </Button>,
          ]}
        />
      )}
    </Space>
  )
}
