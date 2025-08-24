import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card"
import { Button } from "@/shared/components/ui/button"
import { useLanguage } from "@/app/providers/language-provider"
import { cn } from "@/shared/utils/cn"
import { DollarSign, Users, CheckCircle, Star, Plus, FileText, BarChart as BarChartIcon, UserPlus } from "lucide-react"
import * as React from "react"
import { useSupabase } from "@/shared/contexts/supabase-context"

export default function DashboardPage() {
	const { t } = useLanguage()

	const kpis = [
		{ id: 'revenue', title: t('', 'revenue'), value: '', icon: DollarSign, color: 'text-green-600' },
		{ id: 'customers', title: t('', 'newCustomers'), value: '', icon: Users, color: 'text-blue-600' },
		{ id: 'tasks', title: t('', 'tasksCompleted'), value: '', icon: CheckCircle, color: 'text-purple-600' },
		{ id: 'satisfaction', title: t('', 'satisfaction'), value: '', icon: Star, color: 'text-yellow-600' },
	]

	// Revenue (week) widget removed

	type Activity = { id: string; title: string; priority: 'low' | 'medium' | 'high'; time: string }
	const [activities, setActivities] = React.useState<Activity[]>([])

	const { databaseUser } = useSupabase()

	// Load recent events (+/- 48h) and map to activities
	React.useEffect(() => {
		const load = async () => {
			if (!databaseUser?.id) return
			const list = await fetch(`/api/users/${databaseUser.id}/events`).then(r => r.json())
			const now = Date.now()
			const windowMs = 48 * 60 * 60 * 1000
			type SimpleEvent = { id: string; title: string; start: number }
			const items: Activity[] = ((list || []) as Array<any>)
				.map((e: any): SimpleEvent => ({
					id: String(e.id),
					title: String(e.title),
					start: new Date(e.start_at).getTime(),
				}))
				.filter((x: SimpleEvent) => Math.abs(x.start - now) <= windowMs)
				.sort((a: SimpleEvent, b: SimpleEvent) => b.start - a.start)
				.slice(0, 10)
				.map((x: SimpleEvent): Activity => ({
					id: x.id,
					title: `${t('', 'addEvent')}: ${x.title}`,
					priority: 'medium',
					time: new Date(x.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
				}))
			setActivities(items)
		}
		load()
	}, [databaseUser, t])

	React.useEffect(() => {
		const handler = (e: Event | CustomEvent) => {
			const ce = e as CustomEvent<any>
			if (ce.type !== 'imperecta:calendar:add' || !ce.detail) return
			const d = ce.detail
			const dt = new Date(d.date)
			const hh = String(dt.getHours()).padStart(2, '0')
			const mm = String(dt.getMinutes()).padStart(2, '0')
			setActivities((prev): Activity[] => ([
				{ id: String(d.id), title: `${t('', 'addEvent')}: ${String(d.title)}`, priority: 'medium' as const, time: `${hh}:${mm}` },
				...prev,
			]).slice(0, 10))
		}
		window.addEventListener('imperecta:calendar:add', handler as EventListener)
		return () => window.removeEventListener('imperecta:calendar:add', handler as EventListener)
	}, [t])

	const quickActions = [
		{ id: 'qa1', labelKey: 'newInvoice', icon: FileText, color: 'blue' },
		{ id: 'qa2', labelKey: 'addCustomerAction', icon: UserPlus, color: 'green' },
		{ id: 'qa3', labelKey: 'createTaskAction', icon: Plus, color: 'purple' },
		{ id: 'qa4', labelKey: 'reportAction', icon: BarChartIcon, color: 'orange' },
	]

	return (
		<div className="space-y-6">
			{/* Main 4-column grid: left (3 cols) content, right (1 col) stack */}
			<div className="grid grid-cols-1 xl:grid-cols-4 gap-3 items-start">
				{/* Left side: 3 columns */}
				<div className="xl:col-span-3 space-y-3">
					{/* KPI row */}
					<div className="grid grid-cols-2 md:grid-cols-4 gap-3">
						{kpis.map(k => (
							<Card key={k.id} className="dark:neon-glow">
								<CardHeader className="flex flex-row items-center justify-between pb-2">
									<CardTitle className="text-xxl font-semibold">{k.title}</CardTitle>
									<k.icon className={cn("h-5 w-5 opacity-70", k.color)} />
								</CardHeader>
								<CardContent>
									<div className="text-2xl font-bold">{k.value || '—'}</div>
								</CardContent>
							</Card>
						))}
					</div>
					{/* Revenue (week) widget removed */}
				</div>

				{/* Right side: 1 column stack */}
				<div className="xl:col-span-1 space-y-3">
					<Card className="dark:neon-glow">
						<CardHeader className="py-3">
							<CardTitle>{t('', 'quickActions')}</CardTitle>
						</CardHeader>
						<CardContent className="p-3">
							<div className="grid grid-cols-2 gap-2">
								{quickActions.map(a => (
									<Button key={a.id} variant="outline" className="h-12 flex-col gap-1 text-xs">
										<div className={cn("p-2 rounded", `bg-${a.color}-100 text-${a.color}-700`)}>
											<a.icon className="h-4 w-4" />
										</div>
										<span>{t('', a.labelKey as any)}</span>
									</Button>
								))}
							</div>
						</CardContent>
					</Card>

					<Card className="dark:neon-glow">
						<CardHeader className="py-3">
							<CardTitle>{t('', 'activities')}</CardTitle>
						</CardHeader>
						<CardContent className="p-3 text-sm min-h-[360px]">
							<div className="space-y-2">
								{activities.map(act => (
									<div key={act.id} className="flex items-start gap-2 p-2 hover:bg-muted/40 rounded">
										<div className={cn("w-2 h-2 rounded-full mt-2", act.priority === 'high' ? 'bg-orange-500' : act.priority === 'medium' ? 'bg-blue-500' : 'bg-gray-400')} />
										<div className="flex-1">
											<p className="font-medium">{act.title}</p>
											<p className="text-xs text-muted-foreground mt-1">{act.time}</p>
										</div>
									</div>
								))}
							</div>
						</CardContent>
					</Card>

					<Card className="dark:neon-glow">
						<CardHeader className="py-3">
							<CardTitle>AI Insights</CardTitle>
						</CardHeader>
						<CardContent className="p-3 text-sm text-muted-foreground">{/* Empty */}</CardContent>
					</Card>
				</div>
			</div>
		</div>
	)
}
