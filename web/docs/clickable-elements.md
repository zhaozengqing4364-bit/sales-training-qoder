# Clickable Elements Inventory

## 1. Global Sidebar (Main)
Location: `src/components/layout/sidebar.tsx`

### Navigation Links
| Element Label | Icon | Destination | Interaction Type |
| :--- | :--- | :--- | :--- |
| **首页 (Home)** | `Home` | `/` | Navigation (Link) |
| **排行榜 (Leaderboard)** | `BarChart2` | `/leaderboard` | Navigation (Link) |
| **历史 (History)** | `History` | `/history` | Navigation (Link) |
| **管理后台 (Admin)** | `Settings` | `/admin` | Navigation (Link) |

### User Actions
| Element Label | Icon | Action | Interaction Type |
| :--- | :--- | :--- | :--- |
| **User Profile Card** | `User` | Opens "User Profile" Dialog | Modal Trigger |
| **Log Out** | N/A | Logs user out | Button (Dialog Footer) |
| **Edit Profile** | N/A | Opens Edit screen (Mock) | Button (Dialog Footer) |

---

## 2. Admin Sidebar
Location: `src/components/layout/admin-sidebar.tsx`

### Navigation Links
| Element Label | Icon | Destination | Interaction Type |
| :--- | :--- | :--- | :--- |
| **总览 (Overview)** | `LayoutDashboard` | `/admin` | Navigation (Link) |
| **用户管理 (Users)** | `Users` | `/admin/users` | Navigation (Link) |
| **智能体管理 (Agents)** | `Bot` | `/admin/agents` | Navigation (Link) |
| **训练记录 (Records)** | `FileText` | `/admin/records` | Navigation (Link) |
| **系统设置 (Settings)** | `Settings` | `/admin/settings` | Navigation (Link) |
| **操作日志 (Logs)** | `Activity` | `/admin/logs` | Navigation (Link) |

### User Actions
| Element Label | Icon | Action | Interaction Type |
| :--- | :--- | :--- | :--- |
| **Admin Profile Card** | `Shield` | Opens "Admin Access" Dialog | Modal Trigger |
| **Switch User** | N/A | Switches account | Button (Dialog Footer) |
| **Secure Logout** | N/A | Secure logout | Button (Dialog Footer) |

---

## 3. Dashboard Homepage
Location: `src/app/(dashboard)/page.tsx`

### Header Area
| Element Label | Icon | Action | Interaction Type |
| :--- | :--- | :--- | :--- |
| **Early Access v2.4.0** | N/A | Opens "Changelog" Dialog | Modal Trigger |
| **Awesome! (in Dialog)** | N/A | Closes Dialog | Button |
| **User Name (Alexander)** | N/A | Hover Effect Only | Semantic Text |
| **Weekly Stats Card** | `TrendingUp` | Opens "Weekly Stats" Dialog | Modal Trigger |
| **Download Report** | N/A | Download Action (Mock) | Button (Dialog Footer) |
| **Set Goals** | N/A | Goal Setting (Mock) | Button (Dialog Footer) |

### Sales Coach Section (Large Card)
| Element Label | Icon | Action | Interaction Type |
| :--- | :--- | :--- | :--- |
| **Mic Icon** | `Mic` | None (Visual Hover) | Button (Ghost) |
| **开始练习 (Start Practice)** | `ArrowRight` | Opens "Configure Session" Dialog | Modal Trigger |
| **Select Mode (Cold Call)** | `CheckCircle2` | Select Mode | Selection Card |
| **Select Mode (Negotiation)** | N/A | Select Mode | Selection Card |
| **Customer Persona** | N/A | Select Dropdown | `<select>` Input |
| **Launch Simulation** | N/A | Navigates to `/agents/sales` | Navigation (Link) |
| **Persona Avatars (C/T/O/+)** | N/A | Opens "Persona Profile" Dialogs | Modal Trigger |

### Stacked Cards Section
| Element Label | Icon | Action | Interaction Type |
| :--- | :--- | :--- | :--- |
| **PPT 演讲训练 Card** | `Presentation` | Opens "Upload Presentation" Dialog | Modal Trigger |
| **Upload Area** | `Upload` | Triggers File Select | Dashed Area (Button) |
| **Continue to Coach** | N/A | Navigates to `/agents/ppt` | Navigation (Link) |
| **客服培训 (Coming Soon)** | `Headphones` | Opens "Join Waitlist" Dialog | Modal Trigger |
| **Notify Me** | N/A | Submits Email form | Button (Dialog Footer) |

### Recent Activity Section
| Element Label | Icon | Action | Interaction Type |
| :--- | :--- | :--- | :--- |
| **筛选记录 (Filter)** | `Filter` | Opens "Filter History" Dialog | Modal Trigger |
| **Apply Filters** | N/A | Applies mock filters | Button (Dialog Footer) |
| **Activity Item (Sales)** | `MoreHorizontal` | Opens "Session Analysis" Dialog | Modal Trigger |
| **Share Analysis** | N/A | Share action | Button (Dialog Footer) |
| **View Full Transcript** | N/A | View action | Button (Dialog Footer) |
| **Activity Item (PPT)** | `MoreHorizontal` | Opens "Presentation Analysis" Dialog | Modal Trigger |
| **Download Slides** | N/A | Download action | Button (Dialog Footer) |
| **Watch Replay** | N/A | Watch action | Button (Dialog Footer) |

---

## 4. General UI Components
found in `src/components/ui/`

*   **GlassCard**: Often used as a clickable container or visual wrapper.
*   **Button**: Used universally for clear actions.
*   **DialogTrigger**: Wraps any element to make it open a modal.
*   **NavLink**: Custom component in Sidebars for handling active states and routing.
