"use client";

import { useParams } from "next/navigation";

import { ContentAssetFormPage } from "@/components/admin/curriculum-practice/content-asset-form-page";

export default function EditCaseItemPage() {
    const params = useParams();
    return <ContentAssetFormPage assetType="case-item" mode="edit" assetId={params.id as string} />;
}
