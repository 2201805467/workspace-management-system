import type { User } from "../api";
import { TaskList } from "../components/TaskList";

export function MyTasks({ user }: { user: User }) {
  return (
    <>
      <span className="eyebrow">رتّب أولوياتك</span>
      <h1>مهامي</h1>
      <p className="muted">المهام المسندة إليك ضمن المشاريع المتاحة لك.</p>
      <TaskList user={user} mine />
    </>
  );
}
