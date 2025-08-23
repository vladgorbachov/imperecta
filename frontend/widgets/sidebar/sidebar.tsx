import { Link, useLocation } from "react-router-dom"
import {
	LayoutDashboard,
	Users,
	DollarSign,
	Settings,
	Boxes,
	PieChart,
	MessageSquare,
	ClipboardList,
	Calendar,
	X,
} from "lucide-react"
import { cn } from "@/shared/utils/cn"
import { Button } from "@/shared/components/ui/button"
// import { ScrollArea } from "@/shared/components/ui/scroll-area"
import { Logo } from "@/shared/components/ui/logo"
import { usePermissions } from "@/shared/hooks/use-permissions"
import { useLanguage } from "@/app/providers/language-provider"

interface SidebarProps {
	open: boolean
	onOpenChange: (open: boolean) => void
}

export function Sidebar({ open, onOpenChange }: SidebarProps) {
	const location = useLocation()
	const { isSuperuser } = usePermissions()
	const { t } = useLanguage()

	const routes = [
		{ label: t('', 'overview'), icon: LayoutDashboard, href: "/dashboard" },
		{ label: t('', 'customers'), icon: Users, href: "/customers" },
		{ label: t('', 'finance'), icon: DollarSign, href: "/finance" },
		{ label: t('', 'projects'), icon: ClipboardList, href: "/projects" },
		{ label: t('', 'team'), icon: Users, href: "/team" },
		{ label: t('', 'operations'), icon: Settings, href: "/operations" },
		{ label: t('', 'inventory'), icon: Boxes, href: "/inventory" },
		{ label: t('', 'communications'), icon: MessageSquare, href: "/communications" },
		{ label: t('', 'marketing'), icon: PieChart, href: "/marketing" },
		{ label: t('', 'aiAssistant'), icon: PieChart, href: "/ai/assistant" },
		{ label: t('', 'calendar'), icon: Calendar, href: "/calendar" },
	]

	return (
		<>
			<div className={cn("fixed inset-0 z-40 bg-background/80 backdrop-blur-sm lg:hidden", open ? "block" : "hidden")} onClick={() => onOpenChange(false)} />
			<div className={cn("sidebar-glass sidebar-contours fixed inset-y-0 left-0 z-50 w-61 p-6 shadow-lg transition-transform duration-300 lg:static lg:z-auto flex flex-col", open ? "translate-x-0" : "-translate-x-full lg:translate-x-0")}> 
				<div className="flex items-center justify-center mb-8">
					<Link to="/" className="flex items-center justify-center w-full"><Logo /></Link>
					<Button variant="ghost" size="icon" className="lg:hidden header-btn absolute right-0" onClick={() => onOpenChange(false)}><X className="h-5 w-5" /></Button>
				</div>
				<div className="flex-1 min-h-0 py-6 overflow-y-auto no-scrollbar">
					<nav className="flex flex-col gap-3">
						{routes.map((route) => (
							<Link key={route.href} to={route.href} className={cn("flex items-center gap-3 rounded-xl px-6 py-3 text-lg font-medium transition-all duration-300 group w-full", location.pathname === route.href ? "glass-card bg-gradient-to-r from-primary/20 to-primary/10 border-primary/30 text-black dark:text-white shadow-lg dark:neon-glow dark:border-glow" : "hover:glass-card hover:bg-muted/50 hover:scale-105 dark:hover:neon-glow")}> 
								<route.icon className={cn("h-6 w-6 transition-colors", location.pathname === route.href ? "text-primary dark:text-glow" : "text-muted-foreground group-hover:text-foreground")} />
								<span className="transition-colors">{route.label}</span>
							</Link>
						))}
					</nav>
				</div>
			</div>
		</>
	)
}
