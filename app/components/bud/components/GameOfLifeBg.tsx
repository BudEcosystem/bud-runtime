'use client';

import { useEffect, useRef } from 'react';

const DESIRED_CELL_COUNT = 15; // Adjust this to control grid density

const GameOfLifeBackground = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const gridRef = useRef<number[][]>([]);

  useEffect(() => {
    const GENERATION_INTERVAL = 1000; // 2 seconds between generations
    const FRAME_RATE = 75; // 50ms between frames for smooth animation
    const MAX_OPACITY = 0.2;
    
    // Use innerWidth/innerHeight for viewport dimensions
    const CELL_SIZE = Math.min(window.innerWidth, window.innerHeight) / DESIRED_CELL_COUNT;
    const GRID_WIDTH = Math.ceil(window.innerWidth / CELL_SIZE);
    const GRID_HEIGHT = Math.ceil(window.innerHeight / CELL_SIZE);
    const CANVAS_WIDTH = window.innerWidth;
    const CANVAS_HEIGHT = window.innerHeight;
    const DEAD_COLOR = '#0d0d0d';

    const canvas = canvasRef.current!;
    const ctx = canvas.getContext('2d')!;
    canvas.width = CANVAS_WIDTH;
    canvas.height = CANVAS_HEIGHT;

    // Initialize random grid with the correct dimensions
    gridRef.current = Array.from({ length: GRID_HEIGHT }, () =>
      Array.from({ length: GRID_WIDTH }, () => Math.random() > 0.8 ? 1 : 0)
    );

    const opacityGrid = Array.from({ length: GRID_HEIGHT }, () =>
      Array.from({ length: GRID_WIDTH }, () => MAX_OPACITY)  // Initialize with max opacity 0.7
    );

    let isTransitioning = false;
    let lastGenerationTime = Date.now();

    const draw = () => {
      const grid = gridRef.current;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      let stillTransitioning = false;
      // Draw cells
      for (let y = 0; y < GRID_HEIGHT; y++) {
        for (let x = 0; x < GRID_WIDTH; x++) {
          // Update opacity with transition
          if (grid[y][x]) {
            if (opacityGrid[y][x] < MAX_OPACITY) {  // Max opacity is 0.7
              opacityGrid[y][x] = Math.min(MAX_OPACITY, opacityGrid[y][x] + 0.1);
              stillTransitioning = true;
            }
          } else {
            if (opacityGrid[y][x] > 0) {
              opacityGrid[y][x] = Math.max(0, opacityGrid[y][x] - 0.1);
              stillTransitioning = true;
            }
          }

          if (opacityGrid[y][x] > 0) {
            const gradient = ctx.createLinearGradient(
              x * CELL_SIZE, y * CELL_SIZE,           // Start point (top)
              x * CELL_SIZE, (y + 1) * CELL_SIZE      // End point (bottom)
            );
            gradient.addColorStop(0, `rgba(255, 255, 255, ${opacityGrid[y][x]})`);
            gradient.addColorStop(1, `rgba(0, 0, 0, ${opacityGrid[y][x]})`);
            ctx.fillStyle = gradient;
            ctx.fillRect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE);
          } else {
            ctx.fillStyle = DEAD_COLOR;
            ctx.fillRect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE);
          }
        }
      }
      
      isTransitioning = stillTransitioning;
      
      // Draw grid lines
      ctx.strokeStyle = '#333333';
      ctx.lineWidth = 1;
      
      // Vertical lines
      for (let x = 0; x <= GRID_WIDTH; x++) {
        ctx.beginPath();
        ctx.moveTo(x * CELL_SIZE, 0);
        ctx.lineTo(x * CELL_SIZE, CANVAS_HEIGHT);
        ctx.stroke();
      }
      
      // Horizontal lines
      for (let y = 0; y <= GRID_HEIGHT; y++) {
        ctx.beginPath();
        ctx.moveTo(0, y * CELL_SIZE);
        ctx.lineTo(CANVAS_WIDTH, y * CELL_SIZE);
        ctx.stroke();
      }
    };

    const nextGeneration = () => {
      const newGrid = gridRef.current.map(arr => [...arr]);
      for (let y = 0; y < GRID_HEIGHT; y++) {
        for (let x = 0; x < GRID_WIDTH; x++) {
          const neighbors = countAliveNeighbors(x, y);
          const alive = gridRef.current[y][x];
          if (alive && (neighbors < 2 || neighbors > 3)) {
            newGrid[y][x] = 0;
          } else if (!alive && neighbors === 3) {
            newGrid[y][x] = 1;
          }
        }
      }
      gridRef.current = newGrid;
    };

    const countAliveNeighbors = (x: number, y: number) => {
      let count = 0;
      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          if (dx === 0 && dy === 0) continue;
          const nx = (x + dx + GRID_WIDTH) % GRID_WIDTH;
          const ny = (y + dy + GRID_HEIGHT) % GRID_HEIGHT;
          count += gridRef.current[ny][nx];
        }
      }
      return count;
    };

    const animate = () => {
      draw();
      
      // Check if it's time for next generation
      const currentTime = Date.now();
      if (currentTime - lastGenerationTime >= GENERATION_INTERVAL) {
        nextGeneration();
        lastGenerationTime = currentTime;
      }
      
      setTimeout(() => requestAnimationFrame(animate), FRAME_RATE);
    };

    animate();
  }, []);

  return (
    <div className='absolute top-0 left-0 w-full h-full overflow-hidden'>
        <div className='absolute z-10 top-0 left-0 w-full h-full bg-black opacity-50 gol-bg'></div>
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        top: '0',
        left: '0',
        width: '100vw',
        height: '100vh',
        zIndex: 0,
        backgroundColor: '#202020',
        opacity: 0.5,
      }}
    />
    </div>
  );
};

export default GameOfLifeBackground;
