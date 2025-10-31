import React from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout as AntLayout, Menu } from 'antd';
import { PlusCircleOutlined, UnorderedListOutlined } from '@ant-design/icons';
import type { MenuProps } from 'antd';
import './style.css';

const { Sider, Content } = AntLayout;

type MenuItem = Required<MenuProps>['items'][number];

const menuItems: MenuItem[] = [
  {
    key: '/',
    icon: <PlusCircleOutlined />,
    label: '创建任务',
  },
  {
    key: '/tasks',
    icon: <UnorderedListOutlined />,
    label: '任务列表',
  },
];

const Layout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  // 处理菜单点击
  const handleMenuClick: MenuProps['onClick'] = (e) => {
    navigate(e.key);
  };

  // 获取当前选中的菜单项
  const getSelectedKeys = () => {
    const path = location.pathname;
    if (path === '/') return ['/'];
    if (path.startsWith('/tasks')) return ['/tasks'];
    return [path];
  };

  return (
    <AntLayout className="admin-layout">
      <Sider
        width={200}
        className="admin-sider"
        theme="dark"
      >
        <Menu
          mode="inline"
          selectedKeys={getSelectedKeys()}
          items={menuItems}
          onClick={handleMenuClick}
          className="admin-menu"
        />
      </Sider>
      <Content className="admin-content">
        <Outlet />
      </Content>
    </AntLayout>
  );
};

export default Layout;
