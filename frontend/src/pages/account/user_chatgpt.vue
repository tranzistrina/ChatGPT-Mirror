<template>
  <t-table
    :data="tableChatgptDetailsData"
    :columns="columnsChatgptDetails"
    row-key="chatgpt_username"
    :loading="tableLoading"
    bordered
    hover
  >
    <template #auth_status="{ row }">
      <t-tag v-if="row.auth_status === false" theme="danger" variant="light"> {{ $t('mirror.k5df2_8fc7_671f') }} </t-tag>
      <t-tag v-if="row.auth_status === true" theme="success" variant="light"> {{ $t('mirror.k8fd0_884c_4e2d') }} </t-tag>
    </template>

    <template #op="slotProps">
      <t-link theme="primary" @click="handleCopyUrl(slotProps.row.mirror_token)"> {{ $t('mirror.k590d_5236') }}</t-link>
    </template>
  </t-table>
</template>

<script setup lang="ts">
import { t } from '@/locales';
import { MessagePlugin, TableProps } from 'tdesign-vue-next';
import { ref } from 'vue';

import RequestApi from '@/api/request';

interface TableChatgptDetailsData {
  mirror_token: string;
  chatgpt_username: string;
  plan_type: string;
}

const tableLoading = ref(false);
const tableChatgptDetailsData = ref<TableChatgptDetailsData[]>([]);

const columnsChatgptDetails: TableProps['columns'] = [
  { colKey: 'chatgpt_username', title: 'ChatGPT', width: 80 },
  { colKey: 'plan_type', title: t('mirror.k7c7b_578b'), width: 30 },
  { colKey: 'auth_status', title: t('mirror.k72b6_6001'), width: 30 },
  { colKey: 'mirror_token', title: 'Mirror Token (' + t('mirror.k7528_4e8e_20_41_50_49_2c_20_8be5_74_6f_6b_65_6e_4e0d_4f1a_53d8_66f4') + ')', width: 100 },
  { colKey: 'op', title: t('mirror.k514d_767b_94fe_63a5'), width: 30 },
];

const getChatGPTDetails = async (user: any) => {
  tableLoading.value = true;
  const GptDetailsUri = `/0x/user/get-mirror-token?user_id=${user.id}`;
  const response = await RequestApi(GptDetailsUri);
  const data = await response.json();
  tableChatgptDetailsData.value = data;
  tableLoading.value = false;
  console.log(data);
};

const handleCopyUrl = (mirrorToken: string) => {
  const notLoginUrl = `${window.location.origin}/api/not-login?user_gateway_token=${mirrorToken}`;
  navigator.clipboard.writeText(notLoginUrl);
  MessagePlugin.success(t('mirror.k590d_5236_6210_529f'));
};

defineExpose({
  getChatGPTDetails,
});
</script>
