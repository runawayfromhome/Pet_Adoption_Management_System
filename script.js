import {createClient} from '@supabase/supabase-js'

const supabaseUrl = 'https://izujsyugsjzajjnoiwct.supabase.co'
const supabaseKey = 'sb_publishable_zbi7tOHne3uefnZDCB2IgA_befN73VD'
const supabase = createClient(supabaseUrl, supabaseKey)