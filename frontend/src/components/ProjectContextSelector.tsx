import { useEffect } from 'react'
import { Select, Space, Typography } from 'antd'
import { useAuthStore } from '../store/useAuthStore'
import { useProjectStore } from '../store/useProjectStore'
import { useProjects } from '../hooks/useProjects'

export default function ProjectContextSelector() {
  const authState = useAuthStore()
  const { activeProjectIds, activeDeptTag, setActiveProjects, setActiveDeptTag } =
    useProjectStore()
  const { data: projects = [] } = useProjects({ scope: 'mine' })

  // useAuthStore は現時点で department_tags を持たないため as any でアクセスし、
  // 将来的に追加された際に自動的に機能するようにする
  const deptTags: string[] = (authState as any)?.department_tags ?? []
  const multipleDepts = deptTags.length > 1

  useEffect(() => {
    if (!activeDeptTag && deptTags.length > 0) {
      setActiveDeptTag(deptTags[0])
    }
  }, [deptTags, activeDeptTag, setActiveDeptTag])

  return (
    <Space
      direction="vertical"
      size={4}
      style={{
        width: '100%',
        padding: '10px 12px',
        borderBottom: '1px solid #f0f0f0',
        background: '#fafafa',
      }}
    >
      <div>
        <Typography.Text
          type="secondary"
          style={{ fontSize: 11, display: 'block', marginBottom: 2 }}
        >
          所属部門
        </Typography.Text>
        <Select
          size="small"
          style={{ width: '100%' }}
          value={activeDeptTag ?? deptTags[0] ?? undefined}
          onChange={setActiveDeptTag}
          disabled={!multipleDepts}
          placeholder="部門未設定"
          options={deptTags.map((t) => ({ value: t, label: t }))}
        />
      </div>
      <div>
        <Typography.Text
          type="secondary"
          style={{ fontSize: 11, display: 'block', marginBottom: 2 }}
        >
          プロジェクト
        </Typography.Text>
        <Select
          mode="multiple"
          size="small"
          style={{ width: '100%' }}
          placeholder="全プロジェクト"
          value={activeProjectIds}
          onChange={setActiveProjects}
          allowClear
          options={projects.map((p) => ({ value: p.id, label: p.name }))}
          maxTagCount={1}
          maxTagTextLength={10}
        />
      </div>
    </Space>
  )
}
