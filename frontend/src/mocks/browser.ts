import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

// 创建MSW worker
export const worker = setupWorker(...handlers);
