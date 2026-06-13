export interface AssetRefPickerOption {
    id: string;
    label: string;
    subtitle?: string;
    status: string;
    editHref: string;
    /** When false, option is shown grayed with a publish link. */
    selectable: boolean;
    publishHint?: string;
}
