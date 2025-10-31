import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Form,
  Input,
  Upload,
  Button,
  Card,
  Typography,
  message,
  Alert,
  Switch,
} from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import type { UploadFile, UploadProps } from 'antd';
import type { AxiosError } from 'axios';
import { createTask } from '../../api/tasks';
import type { ApiErrorResponse } from '../../types';
import './style.css';

const { Title, Text } = Typography;
const { Dragger } = Upload;

const CreateTask: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  // 文件上传配置
  const uploadProps: UploadProps = {
    name: 'file',
    multiple: false,
    fileList,
    beforeUpload: (file) => {
      // 验证文件大小
      const isLt5M = file.size / 1024 / 1024 < 5;
      if (!isLt5M) {
        message.error('文件大小不能超过5MB，请压缩后重试');
        return Upload.LIST_IGNORE;
      }

      // 验证文件格式
      const allowedTypes = [
        'text/csv',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      ];
      const allowedExtensions = ['.csv', '.xls', '.xlsx'];
      const extension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();

      if (
        !allowedTypes.includes(file.type) &&
        !allowedExtensions.includes(extension)
      ) {
        message.error('仅支持CSV或Excel格式文件');
        return Upload.LIST_IGNORE;
      }

      // 构造 UploadFile 对象，保留原始文件
      const uploadFile: UploadFile = {
        uid: file.uid,
        name: file.name,
        status: 'done',
        size: file.size,
        type: file.type,
        originFileObj: file,
      };

      setFileList([uploadFile]);
      setError('');

      // 阻止自动上传
      return false;
    },
    onChange: (info) => {
      const latest = info.fileList.slice(-1);
      setFileList(latest);
    },
    onRemove: () => {
      setFileList([]);
    },
    maxCount: 1,
  };

  // 表单提交
  const handleSubmit = async (values: {
    task_name: string;
    agent_api_url: string;
    enable_correction?: boolean;
  }) => {
    if (fileList.length === 0) {
      message.error('请上传测试数据集文件');
      return;
    }

    const datasetFile = fileList[0]?.originFileObj as File | undefined;
    if (!datasetFile) {
      message.error('文件读取失败，请重新上传');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await createTask({
        task_name: values.task_name,
        agent_api_url: values.agent_api_url,
        dataset_file: datasetFile,
        enable_correction: Boolean(values.enable_correction),
      });

      message.success('任务创建成功');
      navigate('/tasks');
    } catch (err) {
      const axiosError = err as AxiosError<ApiErrorResponse>;
      const errorMessage =
        axiosError.response?.data?.message || '任务创建失败，请重试';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="create-task-card">
      <Title level={3}>创建新的评测任务</Title>

        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          autoComplete="off"
          initialValues={{ enable_correction: false }}
        >
          {/* 任务名称 */}
          <Form.Item
            label="任务名称"
            name="task_name"
            rules={[
              { required: true, message: '请输入任务名称' },
              { max: 64, message: '任务名称不能超过64个字符' },
            ]}
          >
            <Input
              placeholder="例如：A团队XX模型V1.2稳定性测试"
              size="large"
            />
          </Form.Item>

          {/* API URL */}
          <Form.Item
            label="智能体 API URL"
            name="agent_api_url"
            rules={[
              { required: true, message: '请输入智能体API URL' },
              {
                pattern: /^https?:\/\/.+/,
                message: '请输入有效的HTTP或HTTPS地址',
              },
            ]}
          >
            <Input
              placeholder="http://20.17.39.169:11105/aicoapi/gateway/v2/..."
              size="large"
            />
          </Form.Item>

          {/* 文件上传 */}
          <Form.Item
            label="测试数据集 (CSV/Excel)"
            required
            validateStatus={fileList.length === 0 ? undefined : 'success'}
          >
            <Dragger {...uploadProps}>
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
              <p className="ant-upload-hint">
                文件要求：必须包含 'question' 和 'standard_answer' 两列
                <br />
                支持格式：CSV、Excel (.xls, .xlsx)
                <br />
                文件大小：≤ 5MB
              </p>
            </Dragger>
          </Form.Item>

          {/* 启用模型矫正开关 */}
          <Form.Item
            label="启用模型矫正"
            name="enable_correction"
            valuePropName="checked"
            extra="开启后，系统将自动对每次输出进行矫正判定，并在结果中计算准确率。"
          >
            <Switch />
          </Form.Item>

          {/* 错误提示 */}
          {error && (
            <Alert
              message="错误"
              description={error}
              type="error"
              closable
              onClose={() => setError('')}
              style={{ marginBottom: 24 }}
            />
          )}

          {/* 提交按钮 */}
          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              size="large"
              loading={loading}
              block
            >
              {loading ? '创建中...' : '创建任务'}
            </Button>
          </Form.Item>

          {/* 帮助文字 */}
          <Text type="secondary" style={{ fontSize: 12 }}>
            提示：创建任务后，系统将自动开始评测，您可以在任务列表页查看进度。
          </Text>
      </Form>
    </Card>
  );
};

export default CreateTask;
