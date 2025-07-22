import { useEffect, useRef } from "react"

export function LineChart() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    // Установка размеров canvas
    const setCanvasDimensions = () => {
      const parent = canvas.parentElement
      if (parent) {
        canvas.width = parent.clientWidth
        canvas.height = parent.clientHeight
      }
    }
    setCanvasDimensions()
    window.addEventListener("resize", setCanvasDimensions)

    // Данные для графика
    const data = [65, 59, 80, 81, 56, 55, 40, 70, 75, 85, 90, 100]
    const labels = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]

    // Рисуем график
    const drawChart = () => {
      if (!ctx) return

      ctx.clearRect(0, 0, canvas.width, canvas.height)

      const padding = 40
      const chartWidth = canvas.width - padding * 2
      const chartHeight = canvas.height - padding * 2

      // Находим максимальное значение для масштабирования
      const maxValue = Math.max(...data)

      // Рисуем оси
      ctx.beginPath()
      ctx.strokeStyle = "#e2e8f0"
      ctx.moveTo(padding, padding)
      ctx.lineTo(padding, canvas.height - padding)
      ctx.lineTo(canvas.width - padding, canvas.height - padding)
      ctx.stroke()

      // Рисуем линию графика
      ctx.beginPath()
      ctx.strokeStyle = "hsl(221.2 83.2% 53.3%)"
      ctx.lineWidth = 2

      data.forEach((value, index) => {
        const x = padding + (chartWidth / (data.length - 1)) * index
        const y = canvas.height - padding - (value / maxValue) * chartHeight

        if (index === 0) {
          ctx.moveTo(x, y)
        } else {
          ctx.lineTo(x, y)
        }
      })

      ctx.stroke()

      // Добавляем точки на линии
      data.forEach((value, index) => {
        const x = padding + (chartWidth / (data.length - 1)) * index
        const y = canvas.height - padding - (value / maxValue) * chartHeight

        ctx.beginPath()
        ctx.arc(x, y, 4, 0, Math.PI * 2)
        ctx.fillStyle = "hsl(221.2 83.2% 53.3%)"
        ctx.fill()
      })

      // Добавляем подписи по оси X
      ctx.fillStyle = "#64748b"
      ctx.font = "10px sans-serif"
      ctx.textAlign = "center"

      labels.forEach((label, index) => {
        const x = padding + (chartWidth / (labels.length - 1)) * index
        const y = canvas.height - padding + 15
        ctx.fillText(label, x, y)
      })
    }

    drawChart()
    window.addEventListener("resize", drawChart)

    return () => {
      window.removeEventListener("resize", setCanvasDimensions)
      window.removeEventListener("resize", drawChart)
    }
  }, [])

  return <canvas ref={canvasRef} className="w-full h-full" />
}

export function BarChart() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    // Установка размеров canvas
    const setCanvasDimensions = () => {
      const parent = canvas.parentElement
      if (parent) {
        canvas.width = parent.clientWidth
        canvas.height = parent.clientHeight
      }
    }
    setCanvasDimensions()
    window.addEventListener("resize", setCanvasDimensions)

    // Данные для графика
    const data = [65, 59, 80, 81, 56, 55]
    const labels = ["Проект A", "Проект B", "Проект C", "Проект D", "Проект E", "Проект F"]

    // Рисуем график
    const drawChart = () => {
      if (!ctx) return

      ctx.clearRect(0, 0, canvas.width, canvas.height)

      const padding = 40
      const chartWidth = canvas.width - padding * 2
      const chartHeight = canvas.height - padding * 2

      // Находим максимальное значение для масштабирования
      const maxValue = Math.max(...data)

      // Рисуем оси
      ctx.beginPath()
      ctx.strokeStyle = "#e2e8f0"
      ctx.moveTo(padding, padding)
      ctx.lineTo(padding, canvas.height - padding)
      ctx.lineTo(canvas.width - padding, canvas.height - padding)
      ctx.stroke()

      // Рисуем столбцы
      const barWidth = (chartWidth / data.length) * 0.8
      const barSpacing = (chartWidth / data.length) * 0.2

      data.forEach((value, index) => {
        const x = padding + (chartWidth / data.length) * index + barSpacing / 2
        const barHeight = (value / maxValue) * chartHeight
        const y = canvas.height - padding - barHeight

        ctx.fillStyle = "hsl(221.2 83.2% 53.3%)"
        ctx.fillRect(x, y, barWidth, barHeight)
      })

      // Добавляем подписи по оси X
      ctx.fillStyle = "#64748b"
      ctx.font = "10px sans-serif"
      ctx.textAlign = "center"

      labels.forEach((label, index) => {
        const x = padding + (chartWidth / data.length) * index + barWidth / 2 + barSpacing / 2
        const y = canvas.height - padding + 15
        ctx.fillText(label, x, y)
      })
    }

    drawChart()
    window.addEventListener("resize", drawChart)

    return () => {
      window.removeEventListener("resize", setCanvasDimensions)
      window.removeEventListener("resize", drawChart)
    }
  }, [])

  return <canvas ref={canvasRef} className="w-full h-full" />
}
