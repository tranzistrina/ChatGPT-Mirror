<template>
  <div>
    <t-card class="list-card-container">
      <t-row justify="space-between">
        <div class="left-operation-container">
          <t-button @click="showDialog = true">{{ $t('mirror.k5f55_5165') }}</t-button>

          <p v-if="!!selectedRowKeys.length" class="selected-count">
            {{ $t('pages.listBase.select') }} {{ selectedRowKeys.length }} {{ $t('pages.listBase.items') }}
          </p>
        </div>
      </t-row>
      <t-table
        :data="tableData"
        :columns="columns"
        row-key="chatgpt_username"
        :loading="tableLoading"
        :selected-row-keys="selectedRowKeys"
        bordered
        hover
        :pagination="pagination"
        @select-change="onSelectChange"
        @page-change="rehandlePageChange"
      >
        <template #auth_status="{ row }">
          <t-tag v-if="row.auth_status === false" theme="danger" variant="light"> {{ $t('mirror.k5df2_8fc7_671f') }} </t-tag>
          <t-tag v-if="row.auth_status === true" theme="success" variant="light"> {{ $t('mirror.k8fd0_884c_4e2d') }} </t-tag>
        </template>

        <!--
        <template #use_count="{ row }">
          <t-space>
            <div v-for="(v, k) in row.use_count" :key="k">
              <t-tag v-if="k.toString().includes('h')">
                <t-space>
                  <span style="color: #0052c1">{{ k.toString().substring(5, 7) }}:</span>
                  <span>{{ v }}</span>
                </t-space>
              </t-tag>
            </div>
          </t-space>
        </template>
        -->

        <template #expires_at="{ row }">
          {{ TimestampToDate(row.expires_at) }}
        </template>

        <template #updated_at="{ row }">
          {{ TimestampToDate(row.updated_at) }}
        </template>

        <template #access_token_exp="{ row }">
          {{ TimestampToDate(row.access_token_exp * 1000) }}
        </template>

        <template #created_time="{ row }">
          {{ TimestampToDate(row.created_time * 1000) }}
        </template>

        <template #op="slotProps">
          <t-space>
            <!-- <t-link theme="primary" @click="handleUpdate(slotProps.row)">{{ $t('mirror.k66f4_65b0') }}</t-link> -->
            <t-link theme="primary" @click="handleEdit(slotProps.row)">{{ $t('mirror.k7f16_8f91') }}</t-link>

            <t-link theme="danger" @click="handleClickDelete(slotProps.row)">{{ $t('mirror.k5220_9664') }}</t-link>
          </t-space>
        </template>
      </t-table>

      <!-- 录入 Token dialog -->
      <t-dialog v-model:visible="showDialog" :header="$t('mirror.k5f55_5165') + ' ChatGPT Token'" width="50%" :on-confirm="handleAdd">
        <t-form v-loading="loading" :data="newChat" :label-width="0">
          <t-form-item label="Token">
            <div style="display: flex; flex-direction: column; width: 100%">
              <t-textarea
                v-model="newChat.chatgpt_token"
                :autosize="{ minRows: 5, maxRows: 5 }"
                autofocus
                size="large"
                :placeholder="$t('mirror.k8bf7_8f93_5165_20_41_63_63_65_73_73_20_54_6f_6b_65_6e_20_6216_20_53_65_73_73_69_6f_6e_20_54_6f_6b_65_6e_20_6216_20_52_65_66_72_65_73_68_20_54_6f_6b_65_6e_3002_4e00_884c_4e00_4e32')"
              ></t-textarea>
              <span style="font-size: 12px; color: #888">
                <t-link target="_blank" theme="primary" size="small" href="https://chatgpt.com/api/auth/session">
                  Access Token</t-link
                >: {{ $t('mirror.k6709_6548_671f_31_30_5929') }}
              </span>
              <span style="font-size: 12px; color: #888">
                <t-link target="_blank" theme="primary" size="small" :href="ChatgptTokenTutorialUrl"
                  >Session Token</t-link
                >: {{ $t('mirror.k6709_6548_671f_33_30_5929') }}
                <!-- or
                <t-link target="_blank" theme="primary" size="small" :href="ChatgptTokenAuthUrl">{{ $t('mirror.k81ea_52a8_83b7_53d6') }}</t-link> -->
              </span>
              <span style="font-size: 12px; color: #888"> Refresh Token: {{ $t('mirror.k6709_6548_671f_6c38_4e45') }} </span>
            </div>
          </t-form-item>
        </t-form>
      </t-dialog>

      <!-- 编辑 备注信息 -->
      <t-dialog v-model:visible="dialogVisibleEdit" :header="$t('mirror.k7f16_8f91_4fe1_606f')" width="50%" :on-confirm="handleEditConfirm">
        <t-form v-loading="loading" :data="editChatInfo" :label-width="120">
          <t-form-item :label="$t('mirror.k5907_6ce8_4fe1_606f')">
            <t-input v-model="editChatInfo.remark" size="large" :placeholder="$t('mirror.k5907_6ce8_4fe1_606f')"></t-input>
          </t-form-item>
        </t-form>
      </t-dialog>

      <!-- 确认删除 dialog -->
      <t-dialog
        v-model:visible="dialogVisibleDelete"
        :header="$t('mirror.k786e_8ba4_5220_9664_8be5_20_43_68_61_74_47_50_54_20_74_6f_6b_65_6e_20_5417')"
        width="600"
        :on-confirm="handleDelete"
      >
      </t-dialog>
    </t-card>
  </div>
</template>

<script setup lang="ts">
import { t } from '@/locales';
import { MessagePlugin, TableProps } from 'tdesign-vue-next';
import { onMounted, ref } from 'vue';

import RequestApi from '@/api/request';
import { ChatgptTokenTutorialUrl } from '@/constants/index';
import { TimestampToDate } from '@/utils/date';

interface TableData {
  username: string;
  status: number;
  plan_type: string;
  // expires_at: number;
  updated_at: number;
  access_token_exp: number;
}
const selectedRowKeys = ref<TableProps['selectedRowKeys']>([]);
const loading = ref(false);
const tableLoading = ref(false);
const tableData = ref<TableData[]>([]);

const pagination = {
  defaultPageSize: 20,
  total: 0,
  defaultCurrent: 1,
};

const rehandlePageChange = (curr: any) => {
  pagination.defaultCurrent = curr.current;
  pagination.defaultPageSize = curr.pageSize;
  getChatGPTList();
};

const columns: TableProps['columns'] = [
  { colKey: 'row-select', type: 'multiple' },
  { colKey: 'id', title: 'ID', width: 50 },
  { colKey: 'chatgpt_username', title: 'ChatGPT ' + t('mirror.k8d26_53f7'), width: 220, fixed: 'left' },
  { colKey: 'auth_status', title: t('mirror.k72b6_6001'), width: 100, fixed: 'left' },
  { colKey: 'plan_type', title: t('mirror.k7c7b_578b'), width: 100 },
  // { colKey: 'use_count', title: '近期用量', width: 350 },
  { colKey: 'access_token_exp', title: 'Access Token ' + t('mirror.k8fc7_671f_65f6_95f4'), width: 200 },
  { colKey: 'created_time', title: t('mirror.k521b_5efa_65f6_95f4'), width: 200 },
  // { colKey: 'updated_at', title: '最近更新时间', width: 200 },
  { colKey: 'remark', title: t('mirror.k5907_6ce8') },
  { width: 200, colKey: 'op', title: t('mirror.k64cd_4f5c') },
];
const showDialog = ref(false);
const dialogVisibleDelete = ref(false);
const usernameDelete = ref('');
const dialogVisibleEdit = ref(false);

const newChat = ref({ chatgpt_token: '', remark: '' });
const editChatInfo = ref({ remark: '', chatgpt_username: '' });

const ChatgptTokenUrl = '/0x/chatgpt/';

onMounted(async () => {
  await getChatGPTList();
});

const getChatGPTList = async () => {
  // 发送请求获取 Token 列表
  tableLoading.value = true;
  const params: any = {
    page: pagination.defaultCurrent,
    page_size: pagination.defaultPageSize,
  };

  const queryString = new URLSearchParams(params).toString();
  const response = await RequestApi(`${ChatgptTokenUrl}?${queryString}`);

  const data = await response.json();
  // console.log('results', data.results);
  tableData.value = data.results;
  pagination.total = data.count;

  tableLoading.value = false;
};

const addChatToken = async () => {
  // 发送请求添加 Token
  loading.value = true;

  const response = await RequestApi(ChatgptTokenUrl, 'POST', {
    chatgpt_token_list: newChat.value.chatgpt_token.split('\n'),
  });

  const data = await response.json();
  loading.value = false;

  if (response.status !== 200) {
    MessagePlugin.error(JSON.stringify(Object.values(data)[0]));

    // if (data.message.includes('status: 403')) {
    //   window.location.href = '/';
    // }
  } else {
    showDialog.value = false;
    await getChatGPTList();
    newChat.value.chatgpt_token = '';
    MessagePlugin.success(t('mirror.k65b0_589e_6210_529f'));
  }
};

const handleEdit = (row: any) => {
  console.log('row', row.remark);
  editChatInfo.value = { ...row };

  dialogVisibleEdit.value = true;
};

const handleClickDelete = (row: any) => {
  usernameDelete.value = row.chatgpt_username;
  dialogVisibleDelete.value = true;
};

const handleDelete = async () => {
  const response = await RequestApi(ChatgptTokenUrl, 'DELETE', { chatgpt_username: usernameDelete.value });

  const data = await response.json();
  dialogVisibleDelete.value = false;
  usernameDelete.value = '';

  if (response.status !== 200) {
    MessagePlugin.error(JSON.stringify(Object.values(data)[0]));
  } else {
    await getChatGPTList();
    MessagePlugin.success(t('mirror.k5220_9664_6210_529f'));
  }
};

const handleAdd = () => {
  if (newChat.value.chatgpt_token.trim() === '') {
    MessagePlugin.error('Token ' + t('mirror.k4e0d_80fd_4e3a_7a7a'));
  } else {
    addChatToken();
  }
};

const onSelectChange: TableProps['onSelectChange'] = (value, _) => {
  selectedRowKeys.value = value;
  // console.log(value, ctx);
};

const handleEditConfirm = async () => {
  await RequestApi(ChatgptTokenUrl, 'PUT', {
    remark: editChatInfo.value.remark,
    chatgpt_username: editChatInfo.value.chatgpt_username,
  });
  await getChatGPTList();
  MessagePlugin.success(t('mirror.k4fee_6539_6210_529f'));
  dialogVisibleEdit.value = false;
};
</script>

<style lang="less" scoped>
.left-operation-container {
  padding: 6px 0;
  margin-bottom: 16px;

  .selected-count {
    display: inline-block;
    margin-left: 8px;
    color: var(--td-text-color-secondary);
  }
}
</style>
