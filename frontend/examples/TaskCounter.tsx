
import { useState } from 'react'

function App() {
  const [tasks, setTasks] = useState<number>(0)
  const [newTask, setNewTask] = useState<string>('')

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
      <input 
        type="text" 
        placeholder="Add a task" 
        value={newTask}
        onChange={(e) => setNewTask(e.target.value)}
      />
      <button onClick={() => newTask.trim() && setTasks(tasks + 1)}>
        Submit Task
      </button>
      

    </main>
  )
}

export default App
