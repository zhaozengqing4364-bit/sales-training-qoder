"use client";

import { useParams } from "next/navigation";

import { ContentAssetFormPage } from "@/components/admin/curriculum-practice/content-asset-form-page";

export default function EditRoleProfilePage() {
    const params = useParams();
    return <ContentAssetFormPage assetType="role-profile" mode="edit" assetId={params.id as string} />;
}
