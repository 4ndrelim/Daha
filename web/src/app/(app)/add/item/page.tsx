import { Suspense } from "react";
import { ItemForm } from "./item-form";

export default function AddItemPage() {
  return (
    <Suspense>
      <ItemForm />
    </Suspense>
  );
}
