interface CarouselProps {
  children?: React.ReactNode
  node?: unknown
}

export function Carousel({ children }: CarouselProps) {
  return (
    <div className="carousel">
      <div className="carousel__track">
        {children}
      </div>
    </div>
  )
}
