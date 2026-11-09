
import { useState } from 'react'

function App() {
  const [tasks, setTasks] = useState<number>(0)

  return (
    <main>
      <h1>WorkSpace</h1>
      <p>Business & Document Management System</p>

      <h2>Tasks: {tasks}</h2>
      <h3> {tasks === 0 && "no tasks"}</h3>

      <button onClick={() => setTasks(tasks + 1)}>
        Add Task
      </button>

      <button onClick={() => tasks > 0 && setTasks(tasks - 1)}>
        Remove Task
      </button>
      <button onClick={() => setTasks(0)}>
        Reset Tasks number
      </button>

    </main>
  )
}

export default App
