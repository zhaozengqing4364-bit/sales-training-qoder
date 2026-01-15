import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SidebarState {
    isCollapsed: boolean;
    toggleSidebar: () => void;
    setSidebarState: (isOpen: boolean) => void;
}

export const useSidebarStore = create<SidebarState>()(
    persist(
        (set) => ({
            isCollapsed: false,
            toggleSidebar: () => set((state) => ({ isCollapsed: !state.isCollapsed })),
            setSidebarState: (isCollapsed) => set({ isCollapsed }),
        }),
        {
            name: 'sidebar-storage',
        }
    )
);
