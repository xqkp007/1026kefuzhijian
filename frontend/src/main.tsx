import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import 'antd/dist/reset.css'; // Ant Design 样式
import './index.css';
import App from './App.tsx';

const shouldEnableMocking =
  import.meta.env.DEV &&
  import.meta.env.VITE_ENABLE_MSW !== 'false' &&
  import.meta.env.VITE_ENABLE_MSW !== '0';

async function enableMocking() {
  if (!shouldEnableMocking) {
    return;
  }

  const { worker } = await import('./mocks/browser');
  await worker.start({
    onUnhandledRequest: 'bypass', // 忽略未处理的请求
  });
}

async function bootstrap() {
  await enableMocking();

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>
  );
}

void bootstrap();
